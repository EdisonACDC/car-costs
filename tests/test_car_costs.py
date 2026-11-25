"""Tests for Car Costs."""

from __future__ import annotations

from datetime import timedelta

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.car_costs.const import DOMAIN
from custom_components.car_costs.receipt import normalise

TODAY = dt_util.now().date()

BASE = {
    "name": "Kodiaq",
    "purchase_price": 38000,
    "extra_investment": 0,
    "start_date": (TODAY - timedelta(days=30)).isoformat(),
    "start_odometer": 10,
    "odometer_entity": "sensor.kodiaq_km",
    "electricity_price": 0.30,
    "home_energy_entity": "sensor.presa_auto_energy",
    "ref_name": "Passat B8",
    "ref_fuel": "diesel",
    "ref_consumption": 6.0,
    "ref_fuel_price": 1.60,
    "old_car_sale_price": 11000,
    "new_tax": 30,
    "new_insurance": 600,
    "new_maintenance": 300,
    "ref_tax": 265,
    "ref_insurance": 500,
    "ref_maintenance": 700,
}


async def _setup(hass: HomeAssistant, data=None) -> MockConfigEntry:
    hass.states.async_set("sensor.kodiaq_km", "10")
    hass.states.async_set("sensor.presa_auto_energy", "100.0")
    entry = MockConfigEntry(domain=DOMAIN, title="Kodiaq", data=data or BASE)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def val(hass, key):
    return hass.states.get(f"sensor.kodiaq_{key}").state


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    r = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Kodiaq",
            "purchase_price": 38000,
            "extra_investment": 0,
            "start_date": "2026-12-05",
            "start_odometer": 0,
        },
    )
    assert r["step_id"] == "energy"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"electricity_price": 0.32})
    assert r["step_id"] == "reference"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {
            "ref_name": "Passat B8",
            "ref_fuel": "diesel",
            "ref_consumption": 5.8,
            "ref_fuel_price": 1.65,
            "old_car_sale_price": 11700,
        },
    )
    assert r["step_id"] == "fixed"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {
            "new_tax": 0,
            "new_insurance": 0,
            "new_maintenance": 0,
            "ref_tax": 0,
            "ref_insurance": 0,
            "ref_maintenance": 0,
        },
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["title"] == "Kodiaq"
    await hass.async_block_till_done()
    assert hass.states.get("sensor.kodiaq_investment").state == "26300.0"


async def test_options_flow_clears_and_updates(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["step_id"] == "init"
    d = {k: BASE[k] for k in ("purchase_price", "extra_investment", "start_date", "start_odometer")}
    r = await hass.config_entries.options.async_configure(r["flow_id"], {**d, "name": "Kodiaq iV"})
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"electricity_price": 0.25})
    r = await hass.config_entries.options.async_configure(
        r["flow_id"],
        {
            "ref_name": "Passat",
            "ref_fuel": "diesel",
            "ref_consumption": 7.0,
            "ref_fuel_price": 1.60,
            "old_car_sale_price": 12000,
        },
    )
    r = await hass.config_entries.options.async_configure(
        r["flow_id"],
        {
            k: BASE[k]
            for k in (
                "new_tax",
                "new_insurance",
                "new_maintenance",
                "ref_tax",
                "ref_insurance",
                "ref_maintenance",
            )
        },
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.title == "Kodiaq iV"
    tracker = entry.runtime_data
    assert tracker.opt("odometer_entity") is None  # cleared
    assert tracker.opt("ref_consumption") == 7.0


async def test_costs_and_comparison(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    # drive 1000 km
    hass.states.async_set("sensor.kodiaq_km", "1010")
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.kodiaq_km_driven").state) == 1000
    # Passat: 1000 km * 6 l/100 * 1.60 = 96
    assert float(hass.states.get("sensor.kodiaq_old_car_fuel_cost_same_km").state) == 96.0

    # home charging through the plug: 100 -> 110 kWh at 0.30
    hass.states.async_set("sensor.presa_auto_energy", "110.0")
    await hass.async_block_till_done()
    # refuel + public charge
    await hass.services.async_call(
        DOMAIN, "add_refuel", {"liters": 20, "total_cost": 36.0}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "add_charge", {"kwh": 10, "total_cost": 5.9, "location": "public"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "add_charge", {"kwh": 5, "location": "home"}, blocking=True
    )
    await hass.async_block_till_done()

    s = entry.runtime_data.summary()
    assert s.electricity_cost == round(3.0 + 5.9 + 1.5, 2)
    assert s.electricity_kwh == 25
    assert s.energy_cost == round(36 + 10.4, 2)
    assert s.energy_savings == round(96 - 46.4, 2)
    # fixed: (1465 - 930) * 30/365
    assert s.days in (29, 30, 31)
    assert s.fixed_cost_savings == round(535 * s.days / 365, 2)
    assert s.investment == 27000
    assert s.amortization == round(s.total_savings / 27000 * 100, 2)
    assert (
        s.break_even_date is not None
        and s.break_even_date > s.break_even_date.today() - timedelta(days=2)
    )
    assert s.cost_per_100km == round(46.4 / 1000 * 100, 2)
    assert s.avg_fuel_consumption == 2.0

    # delete the refuel
    refuel = [e for e in entry.runtime_data.data["log"] if e["kind"] == "refuel"][0]
    await hass.services.async_call(
        DOMAIN, "delete_entry", {"entry_id": refuel["id"]}, blocking=True
    )
    assert entry.runtime_data.summary().fuel_cost == 0


async def test_meter_reset_and_glitch(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    for v in ("102", "unavailable", "103", "1.0", "900"):
        hass.states.async_set("sensor.presa_auto_energy", v)
        await hass.async_block_till_done()
    # 2 + 1 + 1 (reset to 1.0) ; 900 is a glitch (+899) ignored
    assert entry.runtime_data.data["home_kwh"] == 4.0


async def test_auto_start_odometer(hass: HomeAssistant) -> None:
    entry = await _setup(hass, {**BASE, "start_odometer": 0})
    hass.states.async_set("sensor.kodiaq_km", "60")
    await hass.async_block_till_done()
    assert entry.runtime_data.km_driven() == 50  # baseline was the first reading (10)


async def test_persistence(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    await hass.services.async_call(
        DOMAIN, "add_refuel", {"liters": 30, "total_cost": 50, "odometer": 600}, blocking=True
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.summary().fuel_cost == 50
    assert entry.runtime_data.km_driven() == 590


def test_normalise() -> None:
    r = normalise(
        {
            "kind": "refuel",
            "liters": "42,15",
            "price_per_unit": 1.799,
            "date": "2026-12-07",
            "station": "Aral TBB",
        }
    )
    assert r["total_cost"] == round(42.15 * 1.799, 2) and r["complete"]
    r = normalise({"kwh": 20.5, "total_cost": 12.1})
    assert r["kind"] == "charge" and r["location"] == "public" and r["complete"]
    r = normalise({"kind": "refuel", "total_cost": 50})
    assert not r["complete"]


async def _fake_ai(hass, data):
    calls = []

    async def handler(call: ServiceCall):
        calls.append(call.data)
        return {"conversation_id": "x", "data": data}

    hass.services.async_register(
        "ai_task", "generate_data", handler, supports_response=SupportsResponse.ONLY
    )
    return calls


async def test_scan_receipt_service(hass: HomeAssistant, tmp_path) -> None:
    hass.config.media_dirs = {"local": str(tmp_path)}
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    entry = await _setup(hass)
    calls = await _fake_ai(
        hass,
        {
            "kind": "refuel",
            "liters": 40.0,
            "total_cost": 70.36,
            "date": "2026-12-08",
            "station": "Shell Lauda",
            "fuel": "Super E10",
        },
    )
    photo = tmp_path / "foto.jpg"
    photo.write_bytes(b"\xff\xd8fake")
    resp = await hass.services.async_call(
        DOMAIN, "scan_receipt", {"image": str(photo)}, blocking=True, return_response=True
    )
    assert resp["added"]["liters"] == 40.0
    assert resp["added"]["source"] == "receipt"
    att = calls[0]["attachments"][0]["media_content_id"]
    assert att.startswith("media-source://media_source/local/car_costs/")
    assert entry.runtime_data.summary().fuel_cost == 70.36


async def test_upload_view_and_ws(
    hass: HomeAssistant, hass_client, hass_ws_client, tmp_path
) -> None:
    hass.config.media_dirs = {"local": str(tmp_path)}
    entry = await _setup(hass)
    await _fake_ai(hass, {"kind": "charge", "kwh": 22.0, "total_cost": 13.2})
    client = await hass_client()
    import aiohttp

    form = aiohttp.FormData()
    form.add_field("file", b"\xff\xd8fake", filename="s.jpg", content_type="image/jpeg")
    r = await client.post(f"/api/car_costs/receipt/{entry.entry_id}", data=form)
    assert r.status == 200
    body = await r.json()
    assert body["result"]["kwh"] == 22.0 and body["added"] is None  # preview only
    assert list((tmp_path / "car_costs").iterdir())

    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "car_costs/entries"})
    msg = await ws.receive_json()
    assert msg["success"]
    assert msg["result"]["ref_name"] == "Passat B8"
    assert msg["result"]["summary"]["investment"] == 27000

    # card is served
    r = await client.get("/car_costs_static/car-costs-card.js")
    assert r.status == 200


async def test_scan_without_ai_task(hass: HomeAssistant, hass_client, tmp_path) -> None:
    hass.config.media_dirs = {"local": str(tmp_path)}
    entry = await _setup(hass)
    client = await hass_client()
    import aiohttp

    form = aiohttp.FormData()
    form.add_field("file", b"x", filename="s.jpg")
    r = await client.post(f"/api/car_costs/receipt/{entry.entry_id}", data=form)
    assert r.status == 422
    assert "AI Task" in (await r.json())["error"]


async def test_web_app(hass: HomeAssistant, hass_client, hass_client_no_auth) -> None:
    entry = await _setup(hass)
    anon = await hass_client_no_auth()
    r = await anon.get("/car-costs", allow_redirects=False)
    assert r.status == 302 and r.headers["Location"] == "/car_costs_static/app/index.html"
    for f in ("index.html", "app.js", "manifest.webmanifest", "sw.js", "icon-192.png"):
        assert (await anon.get(f"/car_costs_static/app/{f}")).status == 200
    # data needs a token
    assert (await anon.get("/api/car_costs/overview")).status == 401
    client = await hass_client()
    r = await client.get(f"/api/car_costs/overview?config_entry_id={entry.entry_id}&limit=5")
    body = await r.json()
    assert r.status == 200 and body["title"] == "Kodiaq" and body["summary"]["investment"] == 27000
    assert (await client.get("/api/car_costs/overview?config_entry_id=nope")).status == 404
