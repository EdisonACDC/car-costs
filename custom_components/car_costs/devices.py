"""Phones linked without a Home Assistant account (the model of Family Hub's guest invites).

An admin links a phone from the panel: a name, the cars it may see and what it may do. That gives
a link to the web app with a one-time token in the fragment (the part after ``#`` never reaches a
log). The phone opens it and trades the token for a device token of its own.

Security rules kept here:

* Link and device tokens are random (256 bits) and only their SHA-256 hash is stored, compared in
  constant time. A token is never logged, stored in clear or put in a URL by the server.
* A link works once and for 24 hours. A device token is renewed every 30 days.
* A phone only ever gets the cars and the actions it was given; never an entity, the
  configuration or anything else of Home Assistant.
* A removed device stops working at once.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time as monotime
import uuid
from collections import deque
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import (
    async_response,
    require_admin,
    websocket_command,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PANEL_URL_PATH

LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.devices"

VIEW = "view"
ADD = "add"
EDIT = "edit"
PERMISSIONS = (VIEW, ADD, EDIT)
_RANK = {VIEW: 0, ADD: 1, EDIT: 2}

OPEN = "open"
USED = "used"
REVOKED = "revoked"

INVITE_HOURS = 24
TOKEN_BYTES = 32  # 256 bits
ROTATE_AFTER = timedelta(days=30)
ROTATE_GRACE = timedelta(days=7)
INVITE_KEEP = timedelta(days=7)
MAX_NAME = 40
MAX_DEVICES = 50

REQUEST_MINUTES = 10
MAX_PENDING = 3
REQUESTS_PER_HOUR = 5
LOG_KEEP = 200
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
ACTION = re.compile(r"^CAR_COSTS_(ACCEPT|REJECT)_([A-Za-z0-9_-]{8,64})$")
EVENT_REQUEST = f"{DOMAIN}_phone_request"
_NOT_TEXT = re.compile(r"[<>\[\]()`*_#|\\]")

TEXTS = {
    "it": (
        "Nuovo telefono «{name}» vuole accedere – codice {code}",
        "Accetta",
        "Rifiuta",
        "Apri il pannello Costi Auto",
    ),
    "de": (
        "Neues Handy „{name}“ möchte zugreifen – Code {code}",
        "Annehmen",
        "Ablehnen",
        "Panel Costi Auto öffnen",
    ),
    "en": (
        "New phone “{name}” wants access – code {code}",
        "Accept",
        "Reject",
        "Open the Costi Auto panel",
    ),
}

HUB_KEY = f"{DOMAIN}_devices"
DEVICE_FIELDS = ("id", "name", "label", "activated_at", "last_seen", "entries", "permission")


class PhoneError(Exception):
    """A request that is refused. ``code`` is all the phone is told."""

    def __init__(self, code: str, status: int = 403) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def new_token() -> str:
    """A random token of 256 bits, safe in a URL fragment."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    """The only form in which a token is kept."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same_hash(stored: str | None, candidate: str) -> bool:
    return bool(stored) and hmac.compare_digest(str(stored), candidate)


_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "Mac"),
    ("Macintosh", "Mac"),
    ("Linux", "Linux"),
)
_BROWSERS = (
    ("SamsungBrowser", "Samsung Internet"),
    ("Edg", "Edge"),
    ("Firefox", "Firefox"),
    ("FxiOS", "Firefox"),
    ("OPR/", "Opera"),
    ("Chrome", "Chrome"),
    ("CriOS", "Chrome"),
    ("Safari", "Safari"),
)


def describe_device(user_agent: str) -> str:
    """ "iPhone · Safari", from the browser's own header (never from what the page says)."""
    agent = user_agent or ""
    system = next((name for needle, name in _SYSTEMS if needle in agent), "?")
    browser = next((name for needle, name in _BROWSERS if needle in agent), "Browser")
    return f"{system} · {browser}"


class RateLimiter:
    """At most ``limit`` hits per ``window`` seconds for each key (a device or an address)."""

    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = monotime.monotonic() if now is None else now
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 5000:  # forget idle keys
            for old in [k for k, v in self._hits.items() if not v]:
                del self._hits[old]
        return True


class ActivationGuard:
    """Blocks an address for a while after too many wrong activations."""

    def __init__(self, attempts: int = 10, block_seconds: float = 900.0) -> None:
        self.attempts = attempts
        self.block_seconds = block_seconds
        self._failures: dict[str, list[float]] = {}
        self._blocked: dict[str, float] = {}

    def blocked(self, address: str, now: float | None = None) -> bool:
        now = monotime.monotonic() if now is None else now
        until = self._blocked.get(address)
        if until is None:
            return False
        if now >= until:
            del self._blocked[address]
            self._failures.pop(address, None)
            return False
        return True

    def failed(self, address: str, now: float | None = None) -> None:
        now = monotime.monotonic() if now is None else now
        recent = [t for t in self._failures.get(address, []) if t > now - self.block_seconds]
        recent.append(now)
        self._failures[address] = recent
        if len(recent) >= self.attempts:
            self._blocked[address] = now + self.block_seconds


def _now() -> datetime:
    return dt_util.utcnow()


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


_NAME_CLEAN = re.compile(r"\s+")


def clean_name(value: Any) -> str:
    text = _NAME_CLEAN.sub(" ", str(value or "")).strip()
    if not text or len(text) > MAX_NAME:
        raise PhoneError("invalid", 422)
    return text


def allows(device: dict[str, Any], needed: str) -> bool:
    """Whether a device's permission covers ``needed``."""
    return _RANK.get(str(device.get("permission")), -1) >= _RANK[needed]


class DeviceHub:
    """Links, devices and the limits for the phone API. Lives in ``hass.data[HUB_KEY]``."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.invites: dict[str, dict[str, Any]] = {}
        self.devices: dict[str, dict[str, Any]] = {}
        self.read_limit = RateLimiter(60)
        self.write_limit = RateLimiter(10)
        self.activation = ActivationGuard()
        self.request_limit = RateLimiter(REQUESTS_PER_HOUR, 3600.0)
        self.requests: dict[str, dict[str, Any]] = {}
        self.notify: list[str] = []
        self.log: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.invites = dict(data.get("invites", {}))
        self.devices = dict(data.get("devices", {}))
        self.notify = [str(n) for n in data.get("notify", [])]
        self.log = list(data.get("log", []))[-LOG_KEEP:]
        self._cleanup()

    def _data(self) -> dict[str, Any]:
        return {
            "invites": self.invites,
            "devices": self.devices,
            "notify": self.notify,
            "log": self.log[-LOG_KEEP:],
        }

    async def async_save(self) -> None:
        await self._store.async_save(self._data())

    @callback
    def save_later(self) -> None:
        self._store.async_delay_save(self._data, 30)

    def enabled(self) -> bool:
        """The phone API answers only while there is a device or a link that is not used up."""
        return bool(self.devices) or any(i["status"] == OPEN for i in self.invites.values())

    def _cleanup(self) -> None:
        now = _now()
        for key, invite in list(self.invites.items()):
            closed = _parse(invite.get("closed_at")) or _parse(invite.get("expires_at"))
            if (
                invite["status"] != OPEN
                and closed
                and now - closed > INVITE_KEEP
                or invite["status"] == OPEN
                and (_parse(invite["expires_at"]) or now) < now - INVITE_KEEP
            ):
                del self.invites[key]

    # ----- links (admin) -----------------------------------------------------
    async def async_create_invite(
        self, name: str, entries: list[str], permission: str, replaces: str | None = None
    ) -> tuple[dict[str, Any], str]:
        """A new link. Returns it and its token: the token is shown once and never kept."""
        if permission not in PERMISSIONS:
            raise PhoneError("invalid", 422)
        if (
            len(self.devices) + sum(i["status"] == OPEN for i in self.invites.values())
            >= MAX_DEVICES
        ):
            raise PhoneError("too_many", 429)
        token = new_token()
        now = _now()
        invite = {
            "id": uuid.uuid4().hex,
            "name": clean_name(name),
            "entries": list(dict.fromkeys(entries)),
            "permission": permission,
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(hours=INVITE_HOURS)),
            "status": OPEN,
            "token_hash": token_hash(token),
            "closed_at": None,
            "replaces": replaces if replaces in self.devices else None,
        }
        self.invites[str(invite["id"])] = invite
        await self.async_save()
        return invite, token

    async def async_cancel_invite(self, invite_id: str) -> None:
        invite = self.invites.get(invite_id)
        if invite is None:
            raise PhoneError("not_found", 404)
        invite["status"] = REVOKED
        invite["closed_at"] = _iso(_now())
        await self.async_save()

    def _invite_open(self, invite: dict[str, Any]) -> bool:
        expires = _parse(invite.get("expires_at"))
        return invite["status"] == OPEN and expires is not None and expires > _now()

    def invite_by_hash(self, digest: str) -> dict[str, Any] | None:
        found = None
        for invite in self.invites.values():  # no early exit: the time does not tell which one
            if same_hash(invite.get("token_hash"), digest):
                found = invite
        return found

    # ----- activation (the phone) ----------------------------------------------
    async def async_activate(self, token: str, user_agent: str) -> tuple[dict[str, Any], str]:
        """The phone opened a valid link: it becomes a device. The link is used up at once."""
        invite = self.invite_by_hash(token_hash(token))
        if invite is None or not self._invite_open(invite):
            raise PhoneError("invite_invalid", 403)
        now = _now()
        device, device_token = self._new_device(
            invite["name"], user_agent, invite["entries"], invite["permission"]
        )
        old = invite.get("replaces")
        if isinstance(old, str):
            self.devices.pop(old, None)  # "new phone": the old one stops at once
        invite["status"] = USED
        invite["closed_at"] = _iso(now)
        await self._add_device(device)
        return device, device_token

    def _new_device(
        self, name: str, user_agent: str, entries: list[str], permission: str
    ) -> tuple[dict[str, Any], str]:
        device_token = new_token()
        now = _now()
        device = {
            "id": uuid.uuid4().hex,
            "name": name,
            "label": describe_device(user_agent)[:60],
            "activated_at": _iso(now),
            "last_seen": _iso(now),
            "token_hash": token_hash(device_token),
            "token_at": _iso(now),
            "prev_hash": None,
            "prev_until": None,
            "entries": list(entries),
            "permission": permission,
        }
        return device, device_token

    async def _add_device(self, device: dict[str, Any]) -> None:
        self.devices[device["id"]] = device
        await self.async_save()
        persistent_notification.async_create(
            self.hass,
            f"{device['name']} ({device['label']})",
            title="Car Costs",
            notification_id=f"{DOMAIN}_phone_{device['id']}",
        )

    # ----- access requests (the phone asks, an administrator confirms) -------------
    def _record(self, what: str, request: dict[str, Any]) -> None:
        self.log.append(
            {
                "at": _iso(_now()),
                "event": what,
                "name": request["name"],
                "address": request["address"],
            }
        )
        del self.log[:-LOG_KEEP]
        self.save_later()

    async def async_purge(self) -> None:
        """Requests that waited too long are dropped (and their notifications closed)."""
        now = _now()
        for rid, request in list(self.requests.items()):
            expires = _parse(request["expires_at"])
            if request["status"] == PENDING and (expires is None or expires <= now):
                self._record("expired", request)
                del self.requests[rid]
                await self._close_notices(rid)

    async def async_create_request(
        self, name: str, user_agent: str, address: str
    ) -> dict[str, Any]:
        await self.async_purge()
        if not self.request_limit.allow(f"ip:{address}"):
            raise PhoneError("slow_down", 429)
        if sum(r["status"] == PENDING for r in self.requests.values()) >= MAX_PENDING:
            raise PhoneError("too_many", 429)
        text = _NOT_TEXT.sub("", _NAME_CLEAN.sub(" ", str(name or ""))).strip()[:MAX_NAME]
        now = _now()
        request: dict[str, Any] = {
            "id": secrets.token_urlsafe(16),  # 128 bits
            "name": text or "Telefono",
            "code": f"{secrets.randbelow(10000):04d}",
            "label": describe_device(user_agent)[:60],
            "user_agent": user_agent[:200],
            "address": address,
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(minutes=REQUEST_MINUTES)),
            "status": PENDING,
            "token": None,
        }
        self.requests[request["id"]] = request
        self._record("created", request)
        await self._announce(request)
        return request

    def request_state(self, request_id: str) -> dict[str, Any] | None:
        """What the phone may know: the status and the time left, nothing else."""
        request = self.requests.get(request_id)
        if request is None:
            return None
        expires = _parse(request["expires_at"]) or _now()
        left = int((expires - _now()).total_seconds())
        if request["status"] == PENDING and left <= 0:
            return {"status": "expired"}
        if request["status"] == PENDING:
            return {"status": PENDING, "expires_in": left}
        if request["status"] == APPROVED:
            return {"status": APPROVED, "token": request["token"], "refresh_after": 30 * 86400}
        return {"status": REJECTED}

    async def async_poll(self, request_id: str) -> dict[str, Any] | None:
        """The phone's check. A final answer is given once, then the request is forgotten."""
        state = self.request_state(request_id)
        if state is None:
            return None
        if state["status"] == "expired":
            await self.async_purge()
        elif state["status"] != PENDING:
            del self.requests[request_id]
        return state

    async def async_cancel_request(self, request_id: str) -> bool:
        request = self.requests.get(request_id)
        if request is None or request["status"] != PENDING:
            return False
        self._record("cancelled", request)
        del self.requests[request_id]
        await self._close_notices(request_id)
        return True

    async def async_decide(
        self,
        request_id: str,
        approve: bool,
        permission: str = ADD,
        entries: list[str] | None = None,
    ) -> dict[str, Any]:
        """An administrator accepts or rejects a request that is still waiting."""
        request = self.requests.get(request_id)
        expires = _parse(request["expires_at"]) if request else None
        if request is None or request["status"] != PENDING or expires is None or expires <= _now():
            raise PhoneError("not_found", 404)
        if approve:
            if permission not in PERMISSIONS:
                raise PhoneError("invalid", 422)
            device, token = self._new_device(
                request["name"], request["user_agent"], entries or [], permission
            )
            request["status"] = APPROVED
            request["token"] = token
            await self._add_device(device)
            self._record("approved", request)
        else:
            request["status"] = REJECTED
            self._record("rejected", request)
        await self._close_notices(request_id)
        self.hass.bus.async_fire(
            EVENT_REQUEST,
            {"request_id": request_id, "name": request["name"], "status": request["status"]},
        )
        return request

    def _texts(self) -> tuple[str, str, str, str]:
        return TEXTS.get(self.hass.config.language[:2], TEXTS["en"])

    async def _announce(self, request: dict[str, Any]) -> None:
        text, accept, reject, open_panel = self._texts()
        message = text.format(name=request["name"], code=request["code"])
        persistent_notification.async_create(
            self.hass,
            f"{message}\n\n[{open_panel}](/{PANEL_URL_PATH})",
            title="Costi Auto",
            notification_id=f"{DOMAIN}_request_{request['id']}",
        )
        data = {
            "title": "Costi Auto",
            "message": message,
            "data": {
                "tag": request["id"],
                "actions": [
                    {"action": f"CAR_COSTS_ACCEPT_{request['id']}", "title": accept},
                    {"action": f"CAR_COSTS_REJECT_{request['id']}", "title": reject},
                ],
            },
        }
        for service in self.notify:
            try:
                await self.hass.services.async_call("notify", service, data, blocking=False)
            except Exception:  # noqa: BLE001 - a missing phone must not stop the others
                LOGGER.warning("Could not notify %s", service)
        self.hass.bus.async_fire(
            EVENT_REQUEST,
            {"request_id": request["id"], "name": request["name"], "status": PENDING},
        )

    async def _close_notices(self, request_id: str) -> None:
        persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_request_{request_id}")
        for service in self.notify:
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"message": "clear_notification", "data": {"tag": request_id}},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                LOGGER.warning("Could not clear the notice on %s", service)

    def pending(self) -> list[dict[str, Any]]:
        now = _now()
        return [
            {
                k: r[k]
                for k in ("id", "name", "code", "label", "address", "created_at", "expires_at")
            }
            for r in self.requests.values()
            if r["status"] == PENDING and (_parse(r["expires_at"]) or now) > now
        ]

    def notify_options(self) -> list[str]:
        services = self.hass.services.async_services_for_domain("notify")
        return sorted(s for s in services if s.startswith("mobile_app_"))

    def device_for(self, token: str) -> dict[str, Any] | None:
        digest = token_hash(token)
        now = _now()
        found = None
        for device in self.devices.values():
            if same_hash(device.get("token_hash"), digest):
                found = device
                continue
            until = _parse(device.get("prev_until"))
            if until is not None and until > now and same_hash(device.get("prev_hash"), digest):
                found = device
        return found

    def touch(self, device: dict[str, Any]) -> None:
        device["last_seen"] = _iso(_now())
        self.save_later()

    async def async_rotate_if_due(self, device: dict[str, Any]) -> str | None:
        """A new device token every 30 days (the old one works for 7 more days)."""
        issued = _parse(device.get("token_at"))
        now = _now()
        if issued is not None and now - issued < ROTATE_AFTER:
            return None
        token = new_token()
        device["prev_hash"] = device["token_hash"]
        device["prev_until"] = _iso(now + ROTATE_GRACE)
        device["token_hash"] = token_hash(token)
        device["token_at"] = _iso(now)
        await self.async_save()
        return token

    # ----- devices (admin) -------------------------------------------------------
    async def async_update_device(self, device_id: str, changes: dict[str, Any]) -> None:
        device = self.devices.get(device_id)
        if device is None:
            raise PhoneError("not_found", 404)
        if "name" in changes:
            device["name"] = clean_name(changes["name"])
        if "permission" in changes:
            if changes["permission"] not in PERMISSIONS:
                raise PhoneError("invalid", 422)
            device["permission"] = changes["permission"]
        if "entries" in changes:
            device["entries"] = list(dict.fromkeys(changes["entries"]))
        await self.async_save()

    async def async_remove_device(self, device_id: str) -> None:
        if self.devices.pop(device_id, None) is None:
            raise PhoneError("not_found", 404)
        persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_phone_{device_id}")
        await self.async_save()

    def listing(self) -> dict[str, Any]:
        """What the panel shows: never a hash."""
        devices = [
            {
                k: d[k]
                for k in (
                    "id",
                    "name",
                    "label",
                    "activated_at",
                    "last_seen",
                    "entries",
                    "permission",
                )
            }
            for d in self.devices.values()
        ]
        invites = [
            {k: i[k] for k in ("id", "name", "entries", "permission", "expires_at", "replaces")}
            for i in self.invites.values()
            if self._invite_open(i)
        ]
        return {"devices": devices, "invites": invites}


def hub_of(hass: HomeAssistant) -> DeviceHub:
    hub: DeviceHub = hass.data[HUB_KEY]
    return hub


async def async_setup_devices(hass: HomeAssistant) -> DeviceHub:
    hub = DeviceHub(hass)
    await hub.async_load()
    hass.data[HUB_KEY] = hub

    async def _action(event: Event) -> None:
        """Accept / Reject buttons of the notification on the administrator's phone."""
        match = ACTION.match(str(event.data.get("action", "")))
        if match is None:
            return
        entries = [c["id"] for c in _cars(hass)]
        try:
            await hub.async_decide(match.group(2), match.group(1) == "ACCEPT", ADD, entries)
        except PhoneError:
            return  # unknown, used up or expired: ignored

    async def _tick(_when: datetime) -> None:
        await hub.async_purge()

    hass.bus.async_listen("mobile_app_notification_action", _action)
    stop = async_track_time_interval(hass, _tick, timedelta(minutes=1))

    @callback
    def _stop(_event: Event) -> None:
        stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)
    return hub


# ------------------------------------------------------------------ websocket (admin only)
def _cars(hass: HomeAssistant) -> list[dict[str, str]]:
    return [
        {"id": e.entry_id, "title": e.title}
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
    ]


def _valid_entries(hass: HomeAssistant, entries: list[str]) -> list[str]:
    known = {c["id"] for c in _cars(hass)}
    if not entries or not set(entries) <= known:
        raise PhoneError("invalid", 422)
    return entries


def _fail(connection: ActiveConnection, msg: dict[str, Any], err: PhoneError) -> None:
    connection.send_error(msg["id"], err.code, err.code)


@websocket_command({vol.Required("type"): "car_costs/phones"})
@require_admin
@callback
def ws_phones(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Linked phones, open links and the cars that can be given to a phone."""
    from .network import app_link  # noqa: PLC0415

    connection.send_result(
        msg["id"], {**hub_of(hass).listing(), "cars": _cars(hass), "app": app_link(hass)}
    )


@websocket_command(
    {
        vol.Required("type"): "car_costs/phone_link",
        vol.Required("name"): str,
        vol.Required("entries"): [str],
        vol.Required("permission"): vol.In(PERMISSIONS),
        vol.Optional("replaces"): str,
    }
)
@require_admin
@async_response
async def ws_phone_link(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Make a link for a new phone. The token is returned once, inside the link."""
    from .network import app_link  # noqa: PLC0415

    try:
        entries = _valid_entries(hass, msg["entries"])
        invite, token = await hub_of(hass).async_create_invite(
            msg["name"], entries, msg["permission"], msg.get("replaces")
        )
    except PhoneError as err:
        _fail(connection, msg, err)
        return
    app = app_link(hass)
    if not app["url"]:
        await hub_of(hass).async_cancel_invite(invite["id"])
        connection.send_error(msg["id"], "no_url", "no_url")
        return
    connection.send_result(
        msg["id"],
        {
            "link": f"{app['url']}#c={token}",
            "external": app["external"],
            "expires_at": invite["expires_at"],
            "invite_id": invite["id"],
        },
    )


@websocket_command(
    {
        vol.Required("type"): "car_costs/phone_update",
        vol.Required("device_id"): str,
        vol.Optional("name"): str,
        vol.Optional("permission"): vol.In(PERMISSIONS),
        vol.Optional("entries"): [str],
    }
)
@require_admin
@async_response
async def ws_phone_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        changes: dict[str, Any] = {k: msg[k] for k in ("name", "permission", "entries") if k in msg}
        if "entries" in changes:
            _valid_entries(hass, changes["entries"])
        await hub_of(hass).async_update_device(msg["device_id"], changes)
    except PhoneError as err:
        _fail(connection, msg, err)
        return
    connection.send_result(msg["id"], hub_of(hass).listing())


@websocket_command(
    {
        vol.Required("type"): "car_costs/phone_remove",
        vol.Optional("device_id"): str,
        vol.Optional("invite_id"): str,
    }
)
@require_admin
@async_response
async def ws_phone_remove(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Unlink a phone (it stops working at once) or cancel a link that was not used."""
    try:
        if "device_id" in msg:
            await hub_of(hass).async_remove_device(msg["device_id"])
        elif "invite_id" in msg:
            await hub_of(hass).async_cancel_invite(msg["invite_id"])
        else:
            raise PhoneError("invalid", 422)
    except PhoneError as err:
        _fail(connection, msg, err)
        return
    connection.send_result(msg["id"], hub_of(hass).listing())


def _requests_result(hass: HomeAssistant) -> dict[str, Any]:
    hub = hub_of(hass)
    return {
        "requests": hub.pending(),
        "cars": _cars(hass),
        "notify": hub.notify,
        "notify_options": hub.notify_options(),
        "log": hub.log[-20:][::-1],
    }


@websocket_command({vol.Required("type"): "car_costs/requests"})
@require_admin
@async_response
async def ws_requests(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Access requests that wait, who is told about them, and the latest events."""
    await hub_of(hass).async_purge()
    connection.send_result(msg["id"], _requests_result(hass))


@websocket_command(
    {
        vol.Required("type"): "car_costs/request_decide",
        vol.Required("request_id"): str,
        vol.Required("approve"): bool,
        vol.Optional("permission", default=ADD): vol.In(PERMISSIONS),
        vol.Optional("cars"): [str],
    }
)
@require_admin
@async_response
async def ws_request_decide(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Accept (with permission and cars) or reject a phone's request."""
    try:
        entries = (
            _valid_entries(hass, msg["cars"]) if "cars" in msg else [c["id"] for c in _cars(hass)]
        )
        await hub_of(hass).async_decide(
            msg["request_id"], msg["approve"], msg["permission"], entries
        )
    except PhoneError as err:
        _fail(connection, msg, err)
        return
    connection.send_result(msg["id"], _requests_result(hass))


@websocket_command(
    {vol.Required("type"): "car_costs/request_notify", vol.Required("services"): [str]}
)
@require_admin
@async_response
async def ws_request_notify(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Which phones get the notification for a new request."""
    hub = hub_of(hass)
    known = set(hub.notify_options())
    hub.notify = [s for s in dict.fromkeys(msg["services"]) if s in known]
    await hub.async_save()
    connection.send_result(msg["id"], _requests_result(hass))


COMMANDS = (
    ws_phones,
    ws_phone_link,
    ws_phone_update,
    ws_phone_remove,
    ws_requests,
    ws_request_decide,
    ws_request_notify,
)
