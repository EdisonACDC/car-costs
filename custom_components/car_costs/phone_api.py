"""The phone web app's API, under /api/car_costs/app/.

These views do not use Home Assistant's login (``requires_auth=False``): a phone proves itself with
its own device token in the Authorization header (never in a URL). They only answer about the cars
the device was given, and only do what its permission allows. While there is no linked phone and no
open link, every address here answers 404.
"""

from __future__ import annotations

import json
import logging
import re
from http import HTTPStatus
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.http import HomeAssistantView

from .const import DOMAIN
from .devices import ADD, EDIT, VIEW, DeviceHub, PhoneError, allows, hub_of
from .receipt import MIME_BY_SUFFIX, image_path
from .tracker import CarCostTracker

LOGGER = logging.getLogger(__name__)

BASE = "/api/car_costs/app"
MAX_BODY = 8192
MAX_TOKEN = 128

# The link's token must never reach a log, whatever the log level.
_LINK_IN_URL = re.compile(r"([?&#]c=)[A-Za-z0-9_-]+")


class _HideLink(logging.Filter):
    """For aiohttp's access log: the link code in an address is replaced by ***."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "c=" in message and "car" in message:
            record.msg = _LINK_IN_URL.sub(r"\1***", message)
            record.args = ()
        return True


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}

# service name -> permission it needs
SERVICES = {
    "add_refuel": ADD,
    "add_charge": ADD,
    "update_entry": EDIT,
    "delete_entry": EDIT,
}


def _json(data: Any, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data, ensure_ascii=False),
        status=status,
        content_type="application/json",
        charset="utf-8",
        headers=SECURITY_HEADERS,
    )


def _fail(err: PhoneError) -> web.Response:
    """Only a short code: never a detail of Home Assistant."""
    return _json({"error": err.code, "message": err.code}, err.status)


def _address(request: web.Request) -> str:
    return str(request.remote or "?")


def _bearer(request: web.Request) -> str:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or len(token) > MAX_TOKEN:
        raise PhoneError("unknown", 401)
    return token


async def _body(request: web.Request) -> Any:
    if request.content_type != "application/json":
        raise PhoneError("invalid", HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
    raw = await request.content.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise PhoneError("too_large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as err:
        raise PhoneError("invalid", 422) from err


class _PhoneView(HomeAssistantView):
    requires_auth = False
    cors_allowed = False

    def _hub(self, request: web.Request) -> DeviceHub:
        hub = hub_of(request.app["hass"])
        if not hub.enabled():
            raise PhoneError("not_found", 404)
        return hub

    def _limit(self, hub: DeviceHub, request: web.Request, write: bool, device: str = "") -> None:
        """One hit for the address, or (with ``device``) one for the device."""
        limiter = hub.write_limit if write else hub.read_limit
        key = f"dev:{device}" if device else f"ip:{_address(request)}"
        if not limiter.allow(key):
            raise PhoneError("slow_down", HTTPStatus.TOO_MANY_REQUESTS)

    def _device(
        self, request: web.Request, need: str = VIEW, write: bool = False
    ) -> tuple[DeviceHub, dict[str, Any]]:
        hub = self._hub(request)
        self._limit(hub, request, write)
        device = hub.device_for(_bearer(request))
        if device is None:
            raise PhoneError("unknown", 401)
        self._limit(hub, request, write, device["id"])
        if not allows(device, need):
            raise PhoneError("forbidden", 403)
        hub.touch(device)
        return hub, device

    @staticmethod
    def _cars(hass: HomeAssistant, device: dict[str, Any]) -> list[Any]:
        """The loaded cars this device was given."""
        return [
            e
            for e in hass.config_entries.async_loaded_entries(DOMAIN)
            if e.entry_id in device["entries"]
        ]

    def _tracker(
        self, hass: HomeAssistant, device: dict[str, Any], entry_id: str | None
    ) -> CarCostTracker:
        cars = self._cars(hass, device)
        if not entry_id and len(cars) == 1:
            entry_id = cars[0].entry_id
        for entry in cars:
            if entry.entry_id == entry_id:
                tracker: CarCostTracker = entry.runtime_data
                return tracker
        raise PhoneError("forbidden", 403)  # another car, or none: the same answer


class ActivateView(_PhoneView):
    """POST the link's token, get the phone's own device token."""

    url = f"{BASE}/activate"
    name = "api:car_costs:app:activate"

    async def post(self, request: web.Request) -> web.Response:
        try:
            hub = self._hub(request)
            address = _address(request)
            if hub.activation.blocked(address):
                raise PhoneError("slow_down", HTTPStatus.TOO_MANY_REQUESTS)
            body = await _body(request)
            token = body.get("token") if isinstance(body, dict) else None
            if not isinstance(token, str) or not token or len(token) > MAX_TOKEN:
                hub.activation.failed(address)
                raise PhoneError("invite_invalid", 403)
            try:
                _device, device_token = await hub.async_activate(
                    token, request.headers.get("User-Agent", "")
                )
            except PhoneError:
                hub.activation.failed(address)
                raise
        except PhoneError as err:
            return _fail(err)
        return _json({"token": device_token})


class MeView(_PhoneView):
    """GET who this phone is, what it may do and its cars. Also renews the token when due."""

    url = f"{BASE}/me"
    name = "api:car_costs:app:me"

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            hub, device = self._device(request)
            renewed = await hub.async_rotate_if_due(device)
        except PhoneError as err:
            return _fail(err)
        body: dict[str, Any] = {
            "name": device["name"],
            "permission": device["permission"],
            "cars": [
                {"config_entry_id": e.entry_id, "title": e.title} for e in self._cars(hass, device)
            ],
        }
        if renewed:
            body["token"] = renewed
        return _json(body)


class CarsView(_PhoneView):
    url = f"{BASE}/cars"
    name = "api:car_costs:app:cars"

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            _hub, device = self._device(request)
        except PhoneError as err:
            return _fail(err)
        return _json(
            [{"config_entry_id": e.entry_id, "title": e.title} for e in self._cars(hass, device)]
        )


class OverviewView(_PhoneView):
    url = f"{BASE}/overview"
    name = "api:car_costs:app:overview"

    async def get(self, request: web.Request) -> web.Response:
        from . import overview  # noqa: PLC0415

        hass: HomeAssistant = request.app["hass"]
        try:
            _hub, device = self._device(request)
            tracker = self._tracker(hass, device, request.query.get("config_entry_id"))
        except PhoneError as err:
            return _fail(err)
        try:
            limit = max(1, min(200, int(request.query.get("limit", 15))))
        except ValueError:
            limit = 15
        data = overview(tracker, limit)
        data.pop("app", None)  # the address of Home Assistant is none of the phone's business
        return _json(data)


class HistoryView(_PhoneView):
    url = f"{BASE}/history"
    name = "api:car_costs:app:history"

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            _hub, device = self._device(request)
            tracker = self._tracker(hass, device, request.query.get("config_entry_id"))
        except PhoneError as err:
            return _fail(err)
        try:
            months = max(0, min(120, int(request.query.get("months", 0))))
        except ValueError:
            months = 0
        return _json({"config_entry_id": tracker.entry.entry_id, **tracker.history(months)})


class ImageView(_PhoneView):
    """GET a receipt photo, only of the cars this phone was given."""

    url = f"{BASE}/image/{{entry_id}}"
    name = "api:car_costs:app:image"

    async def get(self, request: web.Request, entry_id: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        try:
            _hub, device = self._device(request)
        except PhoneError as err:
            return _fail(err)
        item = None
        for entry in self._cars(hass, device):
            item = next((e for e in entry.runtime_data.data["log"] if e["id"] == entry_id), None)
            if item:
                break
        path = image_path(hass, item.get("image")) if item else None
        if path is None:
            return _fail(PhoneError("not_found", 404))
        try:
            body = await hass.async_add_executor_job(path.read_bytes)
        except OSError:
            return _fail(PhoneError("not_found", 404))
        return web.Response(
            body=body,
            content_type=MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg"),
            headers={**SECURITY_HEADERS, "Cache-Control": "private, max-age=86400"},
        )


class ReceiptView(_PhoneView):
    """POST a receipt photo; the AI of the car reads it. Needs the permission to add."""

    url = f"{BASE}/receipt/{{entry_id}}"
    name = "api:car_costs:app:receipt"

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        from . import read_receipt_upload  # noqa: PLC0415

        hass: HomeAssistant = request.app["hass"]
        try:
            _hub, device = self._device(request, ADD, write=True)
            tracker = self._tracker(hass, device, entry_id)
        except PhoneError as err:
            return _fail(err)
        body, status = await read_receipt_upload(hass, request, tracker)
        return _json(body, status)


class ServiceView(_PhoneView):
    """POST add_refuel / add_charge / update_entry / delete_entry, as the services take them."""

    url = f"{BASE}/service/{{service}}"
    name = "api:car_costs:app:service"

    async def post(self, request: web.Request, service: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            if service not in SERVICES:
                raise PhoneError("not_found", 404)
            _hub, device = self._device(request, SERVICES[service], write=True)
            data = await _body(request)
            if not isinstance(data, dict):
                raise PhoneError("invalid", 422)
            tracker = self._tracker(hass, device, data.get("config_entry_id"))
        except PhoneError as err:
            return _fail(err)
        data = {**data, "config_entry_id": tracker.entry.entry_id}
        if "image" in data and image_path(hass, data["image"]) is None:
            data.pop("image")  # only a photo that is in <media>/car_costs
        try:
            result = await hass.services.async_call(
                DOMAIN, service, data, blocking=True, return_response=service != "delete_entry"
            )
        except vol.Invalid:
            return _fail(PhoneError("invalid", 422))
        except ServiceValidationError:
            return _fail(PhoneError("not_found", 404))
        except HomeAssistantError:
            return _fail(PhoneError("invalid", 422))
        return _json({"service_response": result})


def register_views(hass: HomeAssistant) -> None:
    logging.getLogger("aiohttp.access").addFilter(_HideLink())
    for view in (
        ActivateView,
        MeView,
        CarsView,
        OverviewView,
        HistoryView,
        ImageView,
        ReceiptView,
        ServiceView,
    ):
        hass.http.register_view(view())
