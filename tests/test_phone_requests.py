"""A phone asks for access and an administrator confirms (0.3.0b6)."""

from __future__ import annotations

import itertools
from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util

from custom_components.car_costs.devices import HUB_KEY, REQUESTS_PER_HOUR

from .test_car_costs import _setup

APP = "/api/car_costs/app"
_IDS = itertools.count(1000)
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605 Safari/604"


async def _send(ws, payload):
    await ws.send_json({"id": next(_IDS), **payload})
    return await ws.receive_json()


async def _ask(client, name="iPhone"):
    res = await client.post(f"{APP}/request", json={"name": name}, headers={"User-Agent": UA})
    return res, (await res.json())


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_request_then_accept_from_the_panel(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth
):
    entry = await _setup(hass)
    client = await hass_client_no_auth()
    res, body = await _ask(client)
    assert res.status == 201
    assert len(body["code"]) == 4 and body["code"].isdigit()
    assert body["expires_in"] == 600 and len(body["request_id"]) >= 20
    rid = body["request_id"]

    # nothing but the state before the decision
    res = await client.get(f"{APP}/request/{rid}")
    state = await res.json()
    assert (
        res.status == 200
        and state["status"] == "pending"
        and set(state) == {"status", "expires_in"}
    )
    assert (await client.get(f"{APP}/cars")).status == 404  # no phone, no API

    ws = await hass_ws_client(hass)
    msg = await _send(ws, {"type": "car_costs/requests"})
    pending = msg["result"]["requests"]
    assert [r["id"] for r in pending] == [rid] and pending[0]["code"] == body["code"]

    msg = await _send(
        ws,
        {
            "type": "car_costs/request_decide",
            "request_id": rid,
            "approve": True,
            "permission": "view",
            "cars": [entry.entry_id],
        },
    )
    assert msg["success"] and msg["result"]["requests"] == []

    res = await client.get(f"{APP}/request/{rid}")
    got = await res.json()
    assert got["status"] == "approved" and len(got["token"]) >= 40 and got["refresh_after"] > 0
    assert (await client.get(f"{APP}/request/{rid}")).status == 404  # delivered once only

    device = got["token"]
    me = await (await client.get(f"{APP}/me", headers=_auth(device))).json()
    assert me["permission"] == "view" and me["name"] == "iPhone"
    assert (await client.get(f"{APP}/overview", headers=_auth(device))).status == 200
    hub = hass.data[HUB_KEY]
    assert device not in str(hub.devices)  # only the hash is kept
    assert [e["event"] for e in hub.log] == ["created", "approved"]


async def test_accept_and_reject_from_the_notification(hass: HomeAssistant, hass_client_no_auth):
    await _setup(hass)
    sent: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_marius", lambda call: sent.append(call))
    hub = hass.data[HUB_KEY]
    hub.notify = ["mobile_app_marius"]
    client = await hass_client_no_auth()

    _res, body = await _ask(client)
    rid = body["request_id"]
    await hass.async_block_till_done()
    first = sent[0].data
    assert body["code"] in first["message"] and first["title"] == "Costi Auto"
    assert first["data"]["tag"] == rid
    assert [a["action"] for a in first["data"]["actions"]] == [
        f"CAR_COSTS_ACCEPT_{rid}",
        f"CAR_COSTS_REJECT_{rid}",
    ]

    hass.bus.async_fire("mobile_app_notification_action", {"action": f"CAR_COSTS_ACCEPT_{rid}"})
    await hass.async_block_till_done()
    state = await (await client.get(f"{APP}/request/{rid}")).json()
    assert state["status"] == "approved"
    device = next(iter(hub.devices.values()))
    assert device["permission"] == "add" and len(device["entries"]) == 1
    assert sent[-1].data["data"] == {"tag": rid}  # the notice is closed

    _res, body = await _ask(client, "Android")
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"CAR_COSTS_REJECT_{body['request_id']}"}
    )
    await hass.async_block_till_done()
    state = await (await client.get(f"{APP}/request/{body['request_id']}")).json()
    assert state == {"status": "rejected"}


async def test_unknown_or_used_notification_actions_are_ignored(
    hass: HomeAssistant, hass_client_no_auth
):
    await _setup(hass)
    client = await hass_client_no_auth()
    _res, body = await _ask(client)
    rid = body["request_id"]
    hub = hass.data[HUB_KEY]
    for action in (
        "CAR_COSTS_ACCEPT_unknownunknown",
        "CAR_COSTS_ACCEPT_",
        "OTHER",
        f"CAR_COSTS_ACCEPT_{rid}x",
    ):
        hass.bus.async_fire("mobile_app_notification_action", {"action": action})
    await hass.async_block_till_done()
    assert not hub.devices
    assert (await (await client.get(f"{APP}/request/{rid}")).json())["status"] == "pending"

    hass.bus.async_fire("mobile_app_notification_action", {"action": f"CAR_COSTS_REJECT_{rid}"})
    await hass.async_block_till_done()
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"CAR_COSTS_ACCEPT_{rid}"})
    await hass.async_block_till_done()
    assert not hub.devices  # a request that was decided cannot be reopened


async def test_expiry_cancel_and_cleanup(hass: HomeAssistant, hass_client_no_auth):
    await _setup(hass)
    client = await hass_client_no_auth()
    hub = hass.data[HUB_KEY]

    _res, body = await _ask(client)
    rid = body["request_id"]
    hub.requests[rid]["expires_at"] = (dt_util.utcnow() - timedelta(seconds=1)).isoformat()
    state = await (await client.get(f"{APP}/request/{rid}")).json()
    assert state == {"status": "expired"}
    assert (await client.get(f"{APP}/request/{rid}")).status == 404
    assert hub.log[-1]["event"] == "expired"

    _res, body = await _ask(client)
    rid = body["request_id"]
    assert (await client.delete(f"{APP}/request/{rid}")).status == 200
    assert (await client.get(f"{APP}/request/{rid}")).status == 404
    assert (await client.delete(f"{APP}/request/{rid}")).status == 404

    _res, body = await _ask(client)  # purged without anyone asking
    hub.requests[body["request_id"]]["expires_at"] = (
        dt_util.utcnow() - timedelta(minutes=1)
    ).isoformat()
    await hub.async_purge()
    assert not hub.requests


async def test_limits_and_validation(hass: HomeAssistant, hass_client_no_auth):
    await _setup(hass)
    client = await hass_client_no_auth()
    hub = hass.data[HUB_KEY]

    for _ in range(3):
        res, _b = await _ask(client)
        assert res.status == 201
    res, body = await _ask(client)
    assert res.status == 429 and body["error"] == "too_many"  # 3 waiting at most

    hub.requests.clear()
    hub.request_limit = type(hub.request_limit)(REQUESTS_PER_HOUR, 3600.0)
    for _ in range(REQUESTS_PER_HOUR):
        res, body = await _ask(client)
        hub.requests.clear()
        assert res.status == 201
    res, body = await _ask(client)
    assert res.status == 429 and body["error"] == "slow_down"  # 5 an hour per address

    res = await client.post(f"{APP}/request", data="x", headers={"Content-Type": "text/plain"})
    assert res.status in (415, 429)
    assert (await client.get(f"{APP}/request/" + "a" * 300)).status in (404, 429)


async def test_name_is_cleaned(hass: HomeAssistant, hass_client_no_auth):
    await _setup(hass)
    client = await hass_client_no_auth()
    _res, body = await _ask(client, "[x](http://evil) <b>iPhone</b>")
    request = next(iter(hass.data[HUB_KEY].requests.values()))
    assert request["id"] == body["request_id"]
    assert not set(request["name"]) & set("[]()<>")
    assert "iPhone" in request["name"]


async def test_only_admins_decide_over_websocket(
    hass: HomeAssistant, hass_client_no_auth, hass_ws_client, hass_admin_user, hass_read_only_user
):
    await _setup(hass)
    client = await hass_client_no_auth()
    _res, body = await _ask(client)
    rid = body["request_id"]

    from pytest_homeassistant_custom_component.common import MockUser  # noqa: PLC0415

    assert isinstance(hass_read_only_user, MockUser)
    from homeassistant.auth.models import Credentials  # noqa: F401,PLC0415

    token = await hass.auth.async_create_refresh_token(hass_read_only_user, "https://x")
    access = hass.auth.async_create_access_token(token)
    ws = await hass_ws_client(hass, access)
    for payload in (
        {"type": "car_costs/requests"},
        {
            "type": "car_costs/request_decide",
            "request_id": rid,
            "approve": True,
            "permission": "edit",
        },
        {"type": "car_costs/request_notify", "services": []},
    ):
        msg = await _send(ws, payload)
        assert not msg["success"] and msg["error"]["code"] == "unauthorized"
    assert (await (await client.get(f"{APP}/request/{rid}")).json())["status"] == "pending"
    assert not hass.data[HUB_KEY].devices
