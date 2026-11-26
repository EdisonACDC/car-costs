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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

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

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.invites = dict(data.get("invites", {}))
        self.devices = dict(data.get("devices", {}))
        self._cleanup()

    def _data(self) -> dict[str, Any]:
        return {"invites": self.invites, "devices": self.devices}

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
        device_token = new_token()
        now = _now()
        device = {
            "id": uuid.uuid4().hex,
            "name": invite["name"],
            "label": describe_device(user_agent)[:60],
            "activated_at": _iso(now),
            "last_seen": _iso(now),
            "token_hash": token_hash(device_token),
            "token_at": _iso(now),
            "prev_hash": None,
            "prev_until": None,
            "entries": list(invite["entries"]),
            "permission": invite["permission"],
        }
        old = invite.get("replaces")
        if isinstance(old, str):
            self.devices.pop(old, None)  # "new phone": the old one stops at once
        invite["status"] = USED
        invite["closed_at"] = _iso(now)
        self.devices[device["id"]] = device
        await self.async_save()
        persistent_notification.async_create(
            self.hass,
            f"{device['name']} ({device['label']})",
            title="Car Costs",
            notification_id=f"{DOMAIN}_phone_{device['id']}",
        )
        return device, device_token

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
    connection.send_result(msg["id"], {**hub_of(hass).listing(), "cars": _cars(hass)})


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


COMMANDS = (ws_phones, ws_phone_link, ws_phone_update, ws_phone_remove)
