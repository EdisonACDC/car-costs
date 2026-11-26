"""Phones linked without a Home Assistant account (0.3.0b4)."""

from __future__ import annotations

import itertools
import json
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.car_costs.const import DOMAIN
from custom_components.car_costs.devices import HUB_KEY, RateLimiter, token_hash

from .test_car_costs import BASE, _setup

APP = "/api/car_costs/app"
_IDS = itertools.count(1)


async def _send(ws, payload):
    """Websocket ids must grow: number every message here."""
    await ws.send_json({"id": next(_IDS), **payload})


REFUEL = {"liters": 40, "total_cost": 70, "station": "Aral"}


async def _second_car(hass: HomeAssistant) -> MockConfigEntry:
    data = {k: v for k, v in BASE.items() if k not in ("odometer_entity", "home_energy_entity")}
    entry = MockConfigEntry(domain=DOMAIN, title="Octavia", data={**data, "name": "Octavia"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _link(ws, entries, permission="edit", name="iPhone Marius", **extra) -> str:
    await _send(
        ws,
        {
            "type": "car_costs/phone_link",
            "name": name,
            "entries": entries,
            "permission": permission,
            **extra,
        },
    )
    msg = await ws.receive_json()
    assert msg["success"], msg
    link = msg["result"]["link"]
    assert "#c=" in link
    return link.split("#c=")[1]


async def _pair(hass, hass_ws_client, client, entries, permission="edit"):
    ws = await hass_ws_client(hass)
    token = await _link(ws, entries, permission)
    res = await client.post(f"{APP}/activate", json={"token": token})
    assert res.status == 200
    return (await res.json())["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_link_activate_and_use(hass: HomeAssistant, hass_ws_client, hass_client_no_auth):
    entry = await _setup(hass)
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client_no_auth()
    ws = await hass_ws_client(hass)
    token = await _link(ws, [entry.entry_id])
    assert len(token) >= 40

    res = await client.post(f"{APP}/activate", json={"token": token})
    assert res.status == 200
    device = (await res.json())["token"]
    assert device != token and len(device) >= 40

    me = await (await client.get(f"{APP}/me", headers=_auth(device))).json()
    assert me["name"] == "iPhone Marius" and me["permission"] == "edit"
    assert me["cars"] == [{"config_entry_id": entry.entry_id, "title": "Kodiaq"}]

    ov = await (await client.get(f"{APP}/overview", headers=_auth(device))).json()
    assert ov["title"] == "Kodiaq" and "app" not in ov
    assert (await client.get(f"{APP}/history", headers=_auth(device))).status == 200

    # the panel lists the phone, never a hash
    await _send(ws, {"type": "car_costs/phones"})
    listing = (await ws.receive_json())["result"]
    assert [d["name"] for d in listing["devices"]] == ["iPhone Marius"]
    assert listing["invites"] == []
    assert "token_hash" not in json.dumps(listing)


async def test_tokens_are_stored_only_as_hashes(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth, hass_storage
):
    entry = await _setup(hass)
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client_no_auth()
    ws = await hass_ws_client(hass)
    token = await _link(ws, [entry.entry_id])
    stored = json.dumps(hass.data[HUB_KEY]._data())
    assert token not in stored and token_hash(token) in stored
    device = (await (await client.post(f"{APP}/activate", json={"token": token})).json())["token"]
    stored = json.dumps(hass.data[HUB_KEY]._data())
    assert device not in stored and token_hash(device) in stored


async def test_bad_missing_used_expired_and_removed_tokens(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth
):
    entry = await _setup(hass)
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client_no_auth()
    ws = await hass_ws_client(hass)
    token = await _link(ws, [entry.entry_id])

    # a wrong link, a used link
    assert (await client.post(f"{APP}/activate", json={"token": "nope"})).status == 403
    device = (await (await client.post(f"{APP}/activate", json={"token": token})).json())["token"]
    assert (await client.post(f"{APP}/activate", json={"token": token})).status == 403

    # no token, a wrong token
    assert (await client.get(f"{APP}/overview")).status == 401
    assert (await client.get(f"{APP}/overview", headers=_auth("wrong"))).status == 401
    assert (await client.get(f"{APP}/overview", headers=_auth(device))).status == 200

    # an expired link (24 h)
    token2 = await _link(ws, [entry.entry_id], name="Late")
    hub = hass.data[HUB_KEY]
    for invite in hub.invites.values():
        if invite["name"] == "Late":
            invite["expires_at"] = (dt_util.utcnow() - timedelta(minutes=1)).isoformat()
    assert (await client.post(f"{APP}/activate", json={"token": token2})).status == 403

    # unlinked from the panel: stops at once
    await _send(ws, {"type": "car_costs/phones"})
    device_id = (await ws.receive_json())["result"]["devices"][0]["id"]
    await _send(ws, {"type": "car_costs/phone_remove", "device_id": device_id})
    assert (await ws.receive_json())["success"]
    assert (await client.get(f"{APP}/overview", headers=_auth(device))).status == 401

    # a cancelled link
    token3 = await _link(ws, [entry.entry_id], name="Cancelled")
    invite_id = next(i["id"] for i in hub.invites.values() if i["name"] == "Cancelled")
    await _send(ws, {"type": "car_costs/phone_remove", "invite_id": invite_id})
    assert (await ws.receive_json())["success"]
    assert (await client.post(f"{APP}/activate", json={"token": token3})).status == 403


async def test_permissions(hass: HomeAssistant, hass_ws_client, hass_client_no_auth):
    entry = await _setup(hass)
    hass.config.external_url = "https://ha.example.com"
    tracker = entry.runtime_data
    client = await hass_client_no_auth()
    eid = entry.entry_id

    view = await _pair(hass, hass_ws_client, client, [eid], "view")
    add = await _pair(hass, hass_ws_client, client, [eid], "add")
    edit = await _pair(hass, hass_ws_client, client, [eid], "edit")

    async def call(token, name, body):
        return await client.post(f"{APP}/service/{name}", json=body, headers=_auth(token))

    # view: reads, cannot add, change or delete, cannot upload a receipt
    assert (await client.get(f"{APP}/overview", headers=_auth(view))).status == 200
    assert (await call(view, "add_refuel", REFUEL)).status == 403
    assert (await call(view, "delete_entry", {"entry_id": "x"})).status == 403
    assert (await client.post(f"{APP}/receipt/{eid}", headers=_auth(view))).status == 403
    assert not tracker.data["log"]

    # add: adds, cannot change or delete
    assert (await call(add, "add_refuel", REFUEL)).status == 200
    item = tracker.data["log"][0]
    assert item["station"] == "Aral"
    assert (await call(add, "update_entry", {"entry_id": item["id"], "station": "X"})).status == 403
    assert (await call(add, "delete_entry", {"entry_id": item["id"]})).status == 403

    # edit: changes and deletes
    assert (
        await call(edit, "update_entry", {"entry_id": item["id"], "station": "Shell"})
    ).status == 200
    assert tracker.data["log"][0]["station"] == "Shell"
    assert (await call(edit, "delete_entry", {"entry_id": item["id"]})).status == 200
    assert not tracker.data["log"]

    # unknown service, unknown field
    assert (await call(edit, "scan_receipt", {})).status == 404
    assert (await call(edit, "add_refuel", {**REFUEL, "evil": 1})).status == 422


async def test_phone_cannot_read_or_change_other_cars(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth
):
    first = await _setup(hass)
    second = await _second_car(hass)
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client_no_auth()
    device = await _pair(hass, hass_ws_client, client, [first.entry_id])

    me = await (await client.get(f"{APP}/me", headers=_auth(device))).json()
    assert [c["title"] for c in me["cars"]] == ["Kodiaq"]
    other = f"config_entry_id={second.entry_id}"
    assert (await client.get(f"{APP}/overview?{other}", headers=_auth(device))).status == 403
    assert (await client.get(f"{APP}/history?{other}", headers=_auth(device))).status == 403
    body = {**REFUEL, "config_entry_id": second.entry_id}
    res = await client.post(f"{APP}/service/add_refuel", json=body, headers=_auth(device))
    assert res.status == 403
    assert not second.runtime_data.data["log"]
    # without naming a car it is the phone's own
    own = await client.post(f"{APP}/service/add_refuel", json=REFUEL, headers=_auth(device))
    assert own.status == 200 and len(first.runtime_data.data["log"]) == 1
    # a photo of the other car is not reachable
    item = second.runtime_data.add_refuel(10, 18)
    assert (await client.get(f"{APP}/image/{item['id']}", headers=_auth(device))).status == 404


async def test_rate_limits_and_activation_block(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth
):
    entry = await _setup(hass)
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client_no_auth()
    device = await _pair(hass, hass_ws_client, client, [entry.entry_id])
    hub = hass.data[HUB_KEY]

    hub.read_limit = RateLimiter(3)
    codes = [(await client.get(f"{APP}/cars", headers=_auth(device))).status for _ in range(5)]
    assert codes[:1] == [200] and 429 in codes
    hub.read_limit = RateLimiter(60)

    hub.write_limit = RateLimiter(2)
    codes = []
    for _ in range(4):
        res = await client.post(f"{APP}/service/add_refuel", json=REFUEL, headers=_auth(device))
        codes.append(res.status)
    assert codes[:2] == [200, 200] and codes[2:] == [429, 429]

    # 10 wrong activations block the address, even for a good link
    ws = await hass_ws_client(hass)
    good = await _link(ws, [entry.entry_id], name="Another")
    for _ in range(10):
        assert (await client.post(f"{APP}/activate", json={"token": "wrong"})).status == 403
    assert (await client.post(f"{APP}/activate", json={"token": good})).status == 429


async def test_token_is_renewed_every_30_days(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth
):
    entry = await _setup(hass)
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client_no_auth()
    device = await _pair(hass, hass_ws_client, client, [entry.entry_id])
    me = await (await client.get(f"{APP}/me", headers=_auth(device))).json()
    assert "token" not in me  # not due

    record = next(iter(hass.data[HUB_KEY].devices.values()))
    record["token_at"] = (dt_util.utcnow() - timedelta(days=31)).isoformat()
    me = await (await client.get(f"{APP}/me", headers=_auth(device))).json()
    new = me["token"]
    assert new != device
    assert (await client.get(f"{APP}/cars", headers=_auth(new))).status == 200
    # the old one still works for the 7 days of grace, then not
    assert (await client.get(f"{APP}/cars", headers=_auth(device))).status == 200
    record["prev_until"] = (dt_util.utcnow() - timedelta(minutes=1)).isoformat()
    assert (await client.get(f"{APP}/cars", headers=_auth(device))).status == 401


async def test_panel_can_rename_change_and_replace(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth
):
    first = await _setup(hass)
    second = await _second_car(hass)
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client_no_auth()
    device = await _pair(hass, hass_ws_client, client, [first.entry_id], "view")
    ws = await hass_ws_client(hass)
    await _send(ws, {"type": "car_costs/phones"})
    device_id = (await ws.receive_json())["result"]["devices"][0]["id"]

    await _send(
        ws,
        {
            "type": "car_costs/phone_update",
            "device_id": device_id,
            "name": "Marius",
            "permission": "add",
            "entries": [first.entry_id, second.entry_id],
        },
    )
    assert (await ws.receive_json())["success"]
    me = await (await client.get(f"{APP}/me", headers=_auth(device))).json()
    assert me["name"] == "Marius" and me["permission"] == "add" and len(me["cars"]) == 2

    # a car that does not exist is refused
    await _send(ws, {"type": "car_costs/phone_update", "device_id": device_id, "entries": ["nope"]})
    assert not (await ws.receive_json())["success"]

    # "new phone": the new link replaces the old device when it is used
    token = await _link(ws, [first.entry_id], "view", name="Marius", replaces=device_id)
    new = (await (await client.post(f"{APP}/activate", json={"token": token})).json())["token"]
    assert (await client.get(f"{APP}/cars", headers=_auth(device))).status == 401
    assert (await client.get(f"{APP}/cars", headers=_auth(new))).status == 200


async def test_link_needs_an_address_and_a_real_car(hass: HomeAssistant, hass_ws_client):
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)
    msg = {"type": "car_costs/phone_link", "name": "P", "permission": "view"}
    await _send(ws, {**msg, "entries": ["nope"]})
    assert not (await ws.receive_json())["success"]
    await _send(ws, {**msg, "entries": []})
    assert not (await ws.receive_json())["success"]
    await _send(ws, {**msg, "entries": [entry.entry_id], "name": " "})
    assert not (await ws.receive_json())["success"]


async def test_nothing_answers_without_phones(hass: HomeAssistant, hass_client_no_auth):
    await _setup(hass)
    client = await hass_client_no_auth()
    assert (await client.get(f"{APP}/overview", headers=_auth("x"))).status == 404
    assert (await client.post(f"{APP}/activate", json={"token": "x"})).status == 404
