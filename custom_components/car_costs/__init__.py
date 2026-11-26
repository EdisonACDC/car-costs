"""Car Costs: track what a car really costs and compare it with your old one."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import BodyPartReader, web
from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AUTO_ADD,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DATE,
    ATTR_ENTRY_ID,
    ATTR_IMAGE,
    ATTR_KWH,
    ATTR_LITERS,
    ATTR_LOCATION,
    ATTR_NOTE,
    ATTR_ODOMETER,
    ATTR_STATION,
    ATTR_TOTAL_COST,
    CARD_FILENAME,
    CONF_AI_TASK_ENTITY,
    CONF_EV_CONSUMPTION,
    DOMAIN,
    EVENT_RECEIPT_SCANNED,
    FRONTEND_URL,
    KIND_REFUEL,
    LOCATION_HOME,
    LOCATION_PUBLIC,
    SERVICE_ADD_CHARGE,
    SERVICE_ADD_REFUEL,
    SERVICE_DELETE_ENTRY,
    SERVICE_SCAN_RECEIPT,
    SERVICE_UPDATE_ENTRY,
    SOURCE_RECEIPT,
    STORAGE_VERSION,
    VERSION,
)
from .panel import async_sync_panel
from .receipt import MIME_BY_SUFFIX, async_read_receipt, async_save_image, image_path
from .tracker import CarCostTracker, parse_day

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
MAX_UPLOAD = 15 * 1024 * 1024

type CarCostsConfigEntry = ConfigEntry[CarCostTracker]

_BASE: dict[Any, Any] = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
_COMMON: dict[Any, Any] = {
    vol.Optional(ATTR_ODOMETER): vol.Coerce(float),
    vol.Optional(ATTR_DATE): cv.string,
    vol.Optional(ATTR_STATION): cv.string,
    vol.Optional(ATTR_NOTE): cv.string,
    vol.Optional(ATTR_IMAGE): cv.string,
}
REFUEL_SCHEMA = vol.Schema(
    {
        **_BASE,
        **_COMMON,
        vol.Required(ATTR_LITERS): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        vol.Required(ATTR_TOTAL_COST): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
CHARGE_SCHEMA = vol.Schema(
    {
        **_BASE,
        **_COMMON,
        vol.Required(ATTR_KWH): vol.All(vol.Coerce(float), vol.Range(min=0.01)),
        vol.Optional(ATTR_TOTAL_COST): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(ATTR_LOCATION, default=LOCATION_PUBLIC): vol.In(
            [LOCATION_HOME, LOCATION_PUBLIC]
        ),
    }
)
DELETE_SCHEMA = vol.Schema({**_BASE, vol.Required(ATTR_ENTRY_ID): cv.string})
_NULLABLE_TEXT = vol.Any(None, cv.string)
UPDATE_SCHEMA = vol.Schema(
    {
        **_BASE,
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Optional(ATTR_LITERS): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        vol.Optional(ATTR_KWH): vol.All(vol.Coerce(float), vol.Range(min=0.01)),
        vol.Optional(ATTR_TOTAL_COST): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(ATTR_LOCATION): vol.In([LOCATION_HOME, LOCATION_PUBLIC]),
        vol.Optional(ATTR_ODOMETER): vol.Any(None, vol.Coerce(float)),
        vol.Optional(ATTR_DATE): cv.string,
        vol.Optional(ATTR_STATION): _NULLABLE_TEXT,
        vol.Optional(ATTR_NOTE): _NULLABLE_TEXT,
        vol.Optional(ATTR_IMAGE): _NULLABLE_TEXT,
    }
)
SCAN_SCHEMA = vol.Schema(
    {
        **_BASE,
        vol.Required(ATTR_IMAGE): vol.Any(
            cv.string,
            vol.Schema(
                {vol.Required("media_content_id"): cv.string},
                extra=vol.ALLOW_EXTRA,
            ),
        ),
        vol.Optional(ATTR_AUTO_ADD, default=True): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services, the upload endpoint and the card."""
    _register_services(hass)
    websocket_api.async_register_command(hass, ws_entries)
    hass.http.register_view(ReceiptUploadView())
    hass.http.register_view(SummaryView())
    hass.http.register_view(HistoryView())
    hass.http.register_view(CarsView())
    hass.http.register_view(ImageView())
    hass.http.register_view(AppRedirectView())
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(Path(__file__).parent / "frontend"), False)]
    )
    frontend.add_extra_js_url(hass, f"{FRONTEND_URL}/{CARD_FILENAME}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CarCostsConfigEntry) -> bool:
    tracker = CarCostTracker(hass, entry)
    await tracker.async_load()
    entry.runtime_data = tracker
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await async_sync_panel(hass)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """The car was deleted: remove its storage file too."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def _async_options_updated(hass: HomeAssistant, entry: CarCostsConfigEntry) -> None:
    # Tracked entities may have changed: reload, then recompute the reference.
    name = entry.options.get("name")
    if name and name != entry.title:
        hass.config_entries.async_update_entry(entry, title=name)
    await hass.config_entries.async_reload(entry.entry_id)
    if (new := hass.config_entries.async_get_entry(entry.entry_id)) and hasattr(
        new, "runtime_data"
    ):
        new.runtime_data.async_options_changed()


async def async_unload_entry(hass: HomeAssistant, entry: CarCostsConfigEntry) -> bool:
    await entry.runtime_data.async_unload()
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await async_sync_panel(hass, leaving=entry)
    return ok


# --------------------------------------------------------------------- helpers
def get_tracker(hass: HomeAssistant, entry_id: str | None) -> CarCostTracker:
    entries = [
        e
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
        if entry_id in (None, "", e.entry_id)
    ]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_found")
    if len(entries) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_required")
    tracker: CarCostTracker = entries[0].runtime_data
    return tracker


async def async_scan(
    hass: HomeAssistant,
    tracker: CarCostTracker,
    media_id: str,
    mime: str,
    auto_add: bool,
) -> dict[str, Any]:
    result = await async_read_receipt(
        hass, media_id, mime, tracker.opt(CONF_AI_TASK_ENTITY) or None
    )
    added = None
    if auto_add and result["complete"]:
        if result["kind"] == KIND_REFUEL:
            added = tracker.add_refuel(
                result["liters"],
                result["total_cost"],
                day=result["date"],
                station=result["station"],
                note=result["fuel"],
                source=SOURCE_RECEIPT,
                image=media_id,
            )
        else:
            added = tracker.add_charge(
                result["kwh"],
                result["total_cost"],
                location=LOCATION_PUBLIC,
                day=result["date"],
                station=result["station"],
                source=SOURCE_RECEIPT,
                image=media_id,
            )
    hass.bus.async_fire(
        EVENT_RECEIPT_SCANNED,
        {"config_entry_id": tracker.entry.entry_id, "result": result, "added": bool(added)},
    )
    return {"result": result, "added": added}


@callback
def _register_services(hass: HomeAssistant) -> None:
    async def add_refuel(call: ServiceCall) -> ServiceResponse:
        d = call.data
        item = get_tracker(hass, d.get(ATTR_CONFIG_ENTRY_ID)).add_refuel(
            d[ATTR_LITERS],
            d[ATTR_TOTAL_COST],
            odometer=d.get(ATTR_ODOMETER),
            day=parse_day(d.get(ATTR_DATE)),
            station=d.get(ATTR_STATION),
            note=d.get(ATTR_NOTE),
            image=d.get(ATTR_IMAGE),
        )
        return {"entry": item}

    async def add_charge(call: ServiceCall) -> ServiceResponse:
        d = call.data
        item = get_tracker(hass, d.get(ATTR_CONFIG_ENTRY_ID)).add_charge(
            d[ATTR_KWH],
            d.get(ATTR_TOTAL_COST),
            location=d[ATTR_LOCATION],
            odometer=d.get(ATTR_ODOMETER),
            day=parse_day(d.get(ATTR_DATE)),
            station=d.get(ATTR_STATION),
            note=d.get(ATTR_NOTE),
            image=d.get(ATTR_IMAGE),
        )
        return {"entry": item}

    async def update_entry(call: ServiceCall) -> ServiceResponse:
        tracker = get_tracker(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        fields = {
            k: v for k, v in call.data.items() if k not in (ATTR_CONFIG_ENTRY_ID, ATTR_ENTRY_ID)
        }
        item = tracker.update(call.data[ATTR_ENTRY_ID], fields)
        if item is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="log_entry_not_found"
            )
        return {"entry": item}

    async def delete_entry(call: ServiceCall) -> None:
        tracker = get_tracker(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        if not tracker.delete(call.data[ATTR_ENTRY_ID]):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="log_entry_not_found"
            )

    async def scan_receipt(call: ServiceCall) -> ServiceResponse:
        tracker = get_tracker(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        image = call.data[ATTR_IMAGE]
        if isinstance(image, dict):
            media_id = image["media_content_id"]
            mime = image.get("media_content_type") or "image/jpeg"
        else:
            media_id, mime = image, "image/jpeg"
        if Path(media_id).is_absolute():  # a file path on the HA host
            path = Path(media_id)
            is_file = await hass.async_add_executor_job(path.is_file)
            if not hass.config.is_allowed_path(str(path)) or not is_file:
                raise ServiceValidationError(f"File not allowed or missing: {media_id}")
            content = await hass.async_add_executor_job(path.read_bytes)
            media_id, mime = await async_save_image(
                hass, content, path.name, tracker.entry.entry_id
            )
        return await async_scan(hass, tracker, media_id, mime, call.data[ATTR_AUTO_ADD])

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_REFUEL, add_refuel, REFUEL_SCHEMA, SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_CHARGE, add_charge, CHARGE_SCHEMA, SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, SERVICE_DELETE_ENTRY, delete_entry, DELETE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_ENTRY, update_entry, UPDATE_SCHEMA, SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SCAN_RECEIPT, scan_receipt, SCAN_SCHEMA, SupportsResponse.OPTIONAL
    )


# ------------------------------------------------------------------ websocket
@websocket_command(
    {
        vol.Required("type"): "car_costs/entries",
        vol.Optional("config_entry_id"): str,
        vol.Optional("limit", default=50): int,
    }
)
@callback
def ws_entries(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Return the log and the summary for the card."""
    try:
        tracker = get_tracker(hass, msg.get("config_entry_id"))
    except ServiceValidationError:
        connection.send_error(msg["id"], "not_found", "Car Costs entry not found")
        return
    connection.send_result(msg["id"], overview(tracker, msg["limit"]))


def app_link(hass: HomeAssistant) -> dict[str, Any]:
    """Address of the phone web app: the external one (Nabu Casa / external_url) if there is one."""
    for external in (True, False):
        try:
            base = get_url(
                hass,
                allow_internal=not external,
                allow_external=external,
                allow_cloud=external,
                prefer_external=external,
            )
        except NoURLAvailableError:
            continue
        return {"url": f"{base.rstrip('/')}/car-costs", "external": external}
    return {"url": None, "external": False}


def overview(tracker: CarCostTracker, limit: int = 50) -> dict[str, Any]:
    """Everything the card and the web app show."""
    s = tracker.summary()
    summary = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in vars(s).items()}
    entries = [{**e, "has_image": bool(e.get("image"))} for e in tracker.recent(limit)]
    last_station = next(
        (
            e["station"]
            for e in reversed(tracker.data["log"])
            if e["kind"] == KIND_REFUEL and e.get("station")
        ),
        None,
    )
    return {
        "config_entry_id": tracker.entry.entry_id,
        "title": tracker.entry.title,
        "version": VERSION,
        "app": app_link(tracker.hass),
        "start_date": tracker.start_date.isoformat(),
        "ref_name": tracker.opt("ref_name"),
        "ref_fuel": tracker.opt("ref_fuel"),
        "ref_consumption": tracker.opt("ref_consumption"),
        "electricity_price": tracker.electricity_price,
        "ref_fuel_price": tracker.ref_fuel_price,
        "ev_consumption": tracker.opt(CONF_EV_CONSUMPTION),
        "has_home_meter": bool(tracker.opt("home_energy_entity")),
        "ai_task_available": tracker.hass.services.has_service("ai_task", "generate_data"),
        "last_station": last_station,
        "summary": summary,
        "entries": entries,
    }


class SummaryView(HomeAssistantView):
    """GET the overview (used by the web app, which talks REST)."""

    url = "/api/car_costs/overview"
    name = "api:car_costs:overview"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            tracker = get_tracker(hass, request.query.get("config_entry_id"))
        except ServiceValidationError:
            return self.json_message("Car Costs entry not found", 404)
        try:
            limit = max(1, min(200, int(request.query.get("limit", 15))))
        except ValueError:
            limit = 15
        return self.json(overview(tracker, limit))


class CarsView(HomeAssistantView):
    """GET the cars that are set up (the web app lets you switch between them)."""

    url = "/api/car_costs/cars"
    name = "api:car_costs:cars"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        return self.json(
            [
                {"config_entry_id": e.entry_id, "title": e.title}
                for e in hass.config_entries.async_loaded_entries(DOMAIN)
            ]
        )


class HistoryView(HomeAssistantView):
    """GET monthly aggregates and the daily series for the charts."""

    url = "/api/car_costs/history"
    name = "api:car_costs:history"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            tracker = get_tracker(hass, request.query.get("config_entry_id"))
        except ServiceValidationError:
            return self.json_message("Car Costs entry not found", 404)
        try:
            months = max(0, min(120, int(request.query.get("months", 0))))
        except ValueError:
            months = 0
        return self.json({"config_entry_id": tracker.entry.entry_id, **tracker.history(months)})


class ImageView(HomeAssistantView):
    """GET the receipt photo of a log entry (only files in <media>/car_costs)."""

    url = "/api/car_costs/image/{entry_id}"
    name = "api:car_costs:image"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        item = None
        for config_entry in hass.config_entries.async_loaded_entries(DOMAIN):
            item = next(
                (e for e in config_entry.runtime_data.data["log"] if e["id"] == entry_id),
                None,
            )
            if item:
                break
        path = image_path(hass, item.get("image")) if item else None
        if path is None:
            return self.json_message("Not found", 404)
        try:
            body = await hass.async_add_executor_job(path.read_bytes)
        except OSError:
            return self.json_message("Not found", 404)
        return web.Response(
            body=body,
            content_type=MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg"),
            headers={"Cache-Control": "private, max-age=86400"},
        )


class AppRedirectView(HomeAssistantView):
    """Short address for the web app: /car-costs."""

    url = "/car-costs"
    name = "car_costs:app"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        raise web.HTTPFound(f"{FRONTEND_URL}/app/index.html")


# ----------------------------------------------------------------- upload view
class ReceiptUploadView(HomeAssistantView):
    """POST a receipt photo from the card; returns what the AI read."""

    url = "/api/car_costs/receipt/{entry_id}"
    name = "api:car_costs:receipt"
    requires_auth = True

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            tracker = get_tracker(hass, entry_id)
        except ServiceValidationError:
            return self.json_message("Car Costs entry not found", 404)
        reader = await request.multipart()
        field = await reader.next()
        if not isinstance(field, BodyPartReader) or field.name != "file":
            return self.json_message("Missing file", 400)
        content = bytearray()
        while chunk := await field.read_chunk():
            content.extend(chunk)
            if len(content) > MAX_UPLOAD:
                return self.json_message("File too large", 413)
        auto_add = request.query.get("auto_add") == "1"
        media_id, mime = await async_save_image(
            hass, bytes(content), field.filename or "receipt.jpg", tracker.entry.entry_id
        )
        try:
            result = await async_scan(hass, tracker, media_id, mime, auto_add)
        except HomeAssistantError as err:
            return self.json({"error": str(err), "image": media_id}, 422)
        return self.json(result)
