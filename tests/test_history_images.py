"""Tests for history, midnight snapshots, update_entry, receipt photos (0.3)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.car_costs.const import DOMAIN

from .test_car_costs import BASE, _setup

PHOTO = b"\xff\xd8\xff photo"


def _today():
    # HA's test time zone differs from the machine's: always ask HA.
    return dt_util.now().date()


def _media(tmp_path, hass: HomeAssistant) -> None:
    hass.config.media_dirs = {"local": str(tmp_path)}


def _id(name: str) -> str:
    return f"media-source://media_source/local/car_costs/{name}"


def _photo(tmp_path, name: str = "r.jpg"):
    folder = tmp_path / "car_costs"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(PHOTO)
    return folder / name


# ------------------------------------------------------------------ history
async def test_first_snapshot_and_midnight(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    tracker = entry.runtime_data
    # first start creates the first point of the series
    assert [p["date"] for p in tracker.data["history"]] == [_today().isoformat()]
    assert set(tracker.data["history"][0]) == {
        "date",
        "km",
        "energy_cost",
        "reference_cost",
        "total_savings",
        "home_kwh",
        "home_cost",
    }

    hass.states.async_set("sensor.kodiaq_km", "510")  # 500 km driven
    await hass.async_block_till_done()
    midnight = dt_util.now().replace(hour=0, minute=0, second=5, microsecond=0) + timedelta(days=1)
    async_fire_time_changed(hass, midnight)
    await hass.async_block_till_done()
    history = tracker.data["history"]
    # one point per day: the point of the day that ended is replaced, not added
    assert [p["date"] for p in history] == [_today().isoformat()]
    assert history[0]["km"] == 500
    assert history[0]["reference_cost"] == 48.0  # 500 km * 6 l/100 * 1.60


async def test_snapshot_keeps_one_per_day_and_five_years(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    tracker = entry.runtime_data
    old = (_today() - timedelta(days=6 * 366)).isoformat()
    tracker.data["history"].append({**tracker.data["history"][0], "date": old})
    tracker.snapshot()
    tracker.snapshot()
    dates = [p["date"] for p in tracker.data["history"]]
    assert dates == [_today().isoformat()]  # six-year-old point dropped, no duplicates


async def test_home_daily_and_history_view(
    hass: HomeAssistant, hass_client, hass_client_no_auth
) -> None:
    entry = await _setup(hass)
    hass.states.async_set("sensor.kodiaq_km", "1010")
    hass.states.async_set("sensor.presa_auto_energy", "110.0")  # +10 kWh at 0.30
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, "add_refuel", {"liters": 20, "total_cost": 36.0}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "add_charge", {"kwh": 10, "total_cost": 5.9}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "add_charge", {"kwh": 5, "location": "home"}, blocking=True
    )
    await hass.async_block_till_done()

    day = entry.runtime_data.data["home_daily"][_today().isoformat()]
    assert day == {"kwh": 10.0, "cost": 3.0}

    anon = await hass_client_no_auth()
    assert (await anon.get("/api/car_costs/history")).status == 401
    client = await hass_client()
    r = await client.get(f"/api/car_costs/history?config_entry_id={entry.entry_id}")
    assert r.status == 200
    body = await r.json()
    month = body["months"][-1]
    assert month["month"] == _today().strftime("%Y-%m")
    assert month["fuel_cost"] == 36.0 and month["fuel_liters"] == 20.0
    assert month["public_cost"] == 5.9 and month["public_kwh"] == 10.0
    assert month["home_cost"] == 3.0 + 1.5 and month["home_kwh"] == 15.0  # plug + manual
    assert month["energy_cost"] == round(36 + 5.9 + 4.5, 2)
    assert month["reference_cost"] == 96.0  # 1000 km * 6 l/100 * 1.60, first month
    assert body["home_daily"] == [{"date": _today().isoformat(), "kwh": 10.0, "cost": 3.0}]
    assert body["daily"][-1]["date"] == _today().isoformat()  # live point
    assert body["daily"][-1]["km"] == 1000
    assert body["investment"] == 27000

    assert (await client.get("/api/car_costs/history?config_entry_id=nope")).status == 404
    r = await client.get(f"/api/car_costs/history?months=3&config_entry_id={entry.entry_id}")
    assert len((await r.json())["months"]) <= 3
    r = await client.get("/api/car_costs/history?months=abc")
    assert r.status == 200  # bad number falls back to "all"


async def test_history_months_and_reference_split(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    tracker = entry.runtime_data
    this_first = _today().replace(day=1)
    prev_last = this_first - timedelta(days=1)
    prev_prev_last = prev_last.replace(day=1) - timedelta(days=1)
    tracker.data["history"] = [
        {
            "date": prev_prev_last.isoformat(),
            "km": 100,
            "energy_cost": 5,
            "reference_cost": 30.0,
            "total_savings": 25,
            "home_kwh": 0,
            "home_cost": 0,
        },
        {
            "date": prev_last.isoformat(),
            "km": 400,
            "energy_cost": 20,
            "reference_cost": 50.0,
            "total_savings": 30,
            "home_kwh": 0,
            "home_cost": 0,
        },
    ]
    hass.states.async_set("sensor.kodiaq_km", "1010")  # live reference cost = 96
    await hass.async_block_till_done()
    h = tracker.history()
    by_month = {m["month"]: m["reference_cost"] for m in h["months"]}
    assert by_month[prev_prev_last.strftime("%Y-%m")] == 30.0
    assert by_month[prev_last.strftime("%Y-%m")] == 20.0
    assert by_month[_today().strftime("%Y-%m")] == 46.0
    assert len(tracker.history(1)["months"]) == 1
    assert len(tracker.history(2)["months"]) == 2
    assert [p["date"] for p in tracker.history(1)["daily"]][0] >= this_first.isoformat()


# -------------------------------------------------------------- update_entry
async def test_update_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    await hass.services.async_call(
        DOMAIN, "add_refuel", {"liters": 20, "total_cost": 36.0, "station": "Aral"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "add_charge", {"kwh": 10, "total_cost": 5.0}, blocking=True
    )
    tracker = entry.runtime_data
    refuel = next(e for e in tracker.data["log"] if e["kind"] == "refuel")
    charge = next(e for e in tracker.data["log"] if e["kind"] == "charge")

    resp = await hass.services.async_call(
        DOMAIN,
        "update_entry",
        {
            "entry_id": refuel["id"],
            "liters": 25.5,
            "total_cost": "40,5".replace(",", "."),
            "date": "2026-01-02",
            "station": None,
            "kwh": 99,
            "location": "home",
        },
        blocking=True,
        return_response=True,
    )
    item = resp["entry"]
    assert item["liters"] == 25.5 and item["total_cost"] == 40.5
    assert item["date"] == "2026-01-02" and item["station"] is None
    assert "kwh" not in item and "location" not in item  # not editable on a refuel
    assert tracker.summary().fuel_cost == 40.5
    assert tracker.data["log"][0]["id"] == refuel["id"]  # re-sorted by date

    await hass.services.async_call(
        DOMAIN,
        "update_entry",
        {"entry_id": charge["id"], "kwh": 12, "location": "home", "odometer": 700},
        blocking=True,
    )
    assert charge["kwh"] == 12 and charge["location"] == "home"
    assert tracker.km_driven() == 690  # odometer of the entry counts

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "update_entry", {"entry_id": "nope", "total_cost": 1}, blocking=True
        )


# -------------------------------------------------------------------- images
async def test_image_endpoint(
    hass: HomeAssistant, hass_client, hass_client_no_auth, tmp_path
) -> None:
    _media(tmp_path, hass)
    entry = await _setup(hass)
    _photo(tmp_path)
    (tmp_path / "secret.jpg").write_bytes(b"secret")
    add = lambda image: hass.services.async_call(  # noqa: E731
        DOMAIN,
        "add_refuel",
        {"liters": 10, "total_cost": 18, "image": image},
        blocking=True,
        return_response=True,
    )
    ok = (await add(_id("r.jpg")))["entry"]
    traversal = (await add(_id("../secret.jpg")))["entry"]
    absolute = (await add(str(tmp_path / "secret.jpg")))["entry"]
    missing = (await add(_id("gone.jpg")))["entry"]
    no_image = (
        await hass.services.async_call(
            DOMAIN,
            "add_refuel",
            {"liters": 1, "total_cost": 2},
            blocking=True,
            return_response=True,
        )
    )["entry"]

    anon = await hass_client_no_auth()
    assert (await anon.get(f"/api/car_costs/image/{ok['id']}")).status == 401

    client = await hass_client()
    r = await client.get(f"/api/car_costs/image/{ok['id']}")
    assert r.status == 200 and r.content_type == "image/jpeg" and await r.read() == PHOTO
    for bad in (traversal, absolute, missing, no_image):
        assert (await client.get(f"/api/car_costs/image/{bad['id']}")).status == 404
    assert (await client.get("/api/car_costs/image/doesnotexist")).status == 404

    r = await client.get(f"/api/car_costs/overview?config_entry_id={entry.entry_id}&limit=10")
    flags = {e["id"]: e["has_image"] for e in (await r.json())["entries"]}
    assert flags[ok["id"]] and not flags[no_image["id"]]


async def test_delete_removes_photo(hass: HomeAssistant, tmp_path) -> None:
    _media(tmp_path, hass)
    entry = await _setup(hass)
    photo = _photo(tmp_path)
    outside = tmp_path / "secret.jpg"
    outside.write_bytes(b"secret")
    call = lambda image: hass.services.async_call(  # noqa: E731
        DOMAIN,
        "add_refuel",
        {"liters": 10, "total_cost": 18, "image": image},
        blocking=True,
        return_response=True,
    )
    a = (await call(_id("r.jpg")))["entry"]
    b = (await call(_id("../secret.jpg")))["entry"]

    await hass.services.async_call(DOMAIN, "delete_entry", {"entry_id": b["id"]}, blocking=True)
    await hass.async_block_till_done()
    assert outside.exists()  # never touches files outside /media/car_costs
    await hass.services.async_call(DOMAIN, "delete_entry", {"entry_id": a["id"]}, blocking=True)
    await hass.async_block_till_done()
    assert not photo.exists()
    assert entry.runtime_data.data["log"] == []


async def test_photo_shared_by_two_entries_is_kept(hass: HomeAssistant, tmp_path) -> None:
    _media(tmp_path, hass)
    await _setup(hass)
    photo = _photo(tmp_path)
    call = lambda: hass.services.async_call(  # noqa: E731
        DOMAIN,
        "add_refuel",
        {"liters": 10, "total_cost": 18, "image": _id("r.jpg")},
        blocking=True,
        return_response=True,
    )
    a, b = (await call())["entry"], (await call())["entry"]
    await hass.services.async_call(DOMAIN, "delete_entry", {"entry_id": a["id"]}, blocking=True)
    await hass.async_block_till_done()
    assert photo.exists()
    await hass.services.async_call(DOMAIN, "delete_entry", {"entry_id": b["id"]}, blocking=True)
    await hass.async_block_till_done()
    assert not photo.exists()


async def test_replacing_image_deletes_the_old_one(hass: HomeAssistant, tmp_path) -> None:
    _media(tmp_path, hass)
    await _setup(hass)
    old, new = _photo(tmp_path, "old.jpg"), _photo(tmp_path, "new.jpg")
    item = (
        await hass.services.async_call(
            DOMAIN,
            "add_refuel",
            {"liters": 10, "total_cost": 18, "image": _id("old.jpg")},
            blocking=True,
            return_response=True,
        )
    )["entry"]
    await hass.services.async_call(
        DOMAIN, "update_entry", {"entry_id": item["id"], "image": _id("new.jpg")}, blocking=True
    )
    await hass.async_block_till_done()
    assert not old.exists() and new.exists()


async def test_scan_saves_photo_on_entry(hass: HomeAssistant, hass_client, tmp_path) -> None:
    from .test_car_costs import _fake_ai

    _media(tmp_path, hass)
    entry = await _setup(hass)
    await _fake_ai(
        hass, {"kind": "refuel", "liters": 40.0, "total_cost": 70.0, "date": "2026-12-08"}
    )
    client = await hass_client()
    import aiohttp

    form = aiohttp.FormData()
    form.add_field("file", PHOTO, filename="s.jpg", content_type="image/jpeg")
    body = await (await client.post(f"/api/car_costs/receipt/{entry.entry_id}", data=form)).json()
    media_id = body["result"]["image"]  # what the app passes back when saving
    assert media_id.startswith("media-source://media_source/local/car_costs/")
    await hass.services.async_call(
        DOMAIN, "add_refuel", {"liters": 40, "total_cost": 70, "image": media_id}, blocking=True
    )
    item = entry.runtime_data.data["log"][-1]
    r = await client.get(f"/api/car_costs/image/{item['id']}")
    assert r.status == 200 and await r.read() == PHOTO


# --------------------------------------------------------------- ev share etc
async def test_ev_share_only_when_configured(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    tracker = entry.runtime_data
    hass.states.async_set("sensor.kodiaq_km", "1010")
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, "add_charge", {"kwh": 110, "total_cost": 30}, blocking=True
    )
    assert tracker.summary().ev_share_pct is None  # option not set

    hass.config_entries.async_update_entry(entry, options={"ev_consumption": 22})
    assert tracker.summary().ev_share_pct == 50.0  # 110 kWh / 22 * 100 = 500 km of 1000
    hass.config_entries.async_update_entry(entry, options={"ev_consumption": 5})
    assert tracker.summary().ev_share_pct == 100.0  # capped


async def test_overview_has_new_fields(hass: HomeAssistant, hass_client) -> None:
    entry = await _setup(hass, {**BASE, "ev_consumption": 22})
    await hass.services.async_call(
        DOMAIN, "add_refuel", {"liters": 10, "total_cost": 18, "station": "Aral"}, blocking=True
    )
    hass.config.external_url = "https://ha.example.com"
    client = await hass_client()
    body = await (
        await client.get(f"/api/car_costs/overview?config_entry_id={entry.entry_id}")
    ).json()
    assert body["app"] == {"url": "https://ha.example.com/car-costs", "external": True}
    assert body["ev_consumption"] == 22 and body["last_station"] == "Aral"
    assert body["ref_fuel"] == "diesel" and body["version"] == "0.3.0b4"
    assert body["ai_task_available"] is False
    assert "ev_share_pct" in body["summary"]


async def test_remove_entry_deletes_storage(hass: HomeAssistant, hass_storage) -> None:
    entry = await _setup(hass)
    key = f"{DOMAIN}.{entry.entry_id}"
    await hass.config_entries.async_unload(entry.entry_id)  # writes the file
    assert key in hass_storage
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_cars_view(hass: HomeAssistant, hass_client, hass_client_no_auth) -> None:
    entry = await _setup(hass)
    assert (await (await hass_client_no_auth()).get("/api/car_costs/cars")).status == 401
    r = await (await hass_client()).get("/api/car_costs/cars")
    assert await r.json() == [{"config_entry_id": entry.entry_id, "title": "Kodiaq"}]


async def test_new_web_app_files_are_served(hass: HomeAssistant, hass_client_no_auth) -> None:
    await _setup(hass)
    anon = await hass_client_no_auth()
    for f in (
        "index.html",
        "app.css",
        "app.js",
        "auth.js",
        "i18n.js",
        "ui.js",
        "forms.js",
        "charts.js",
        "sw.js",
        "manifest.webmanifest",
        "icon-192.png",
        "icon-512.png",
        "icon-maskable-512.png",
        "apple-touch-icon.png",
        "splash/splash-1170x2532.png",
    ):
        assert (await anon.get(f"/car_costs_static/app/{f}")).status == 200, f


async def test_saved_photos_in_the_same_second_do_not_collide(
    hass: HomeAssistant, tmp_path
) -> None:
    from custom_components.car_costs.receipt import async_save_image

    _media(tmp_path, hass)
    a, _ = await async_save_image(hass, b"one", "a.jpg", "abcdef123")
    b, _ = await async_save_image(hass, b"two", "a.jpg", "abcdef123")
    assert a != b
    assert len(list((tmp_path / "car_costs").iterdir())) == 2


async def test_midnight_deletes_old_orphan_photos(hass: HomeAssistant, tmp_path) -> None:
    import os
    import time

    _media(tmp_path, hass)
    entry = await _setup(hass)
    used = _photo(tmp_path, "used.jpg")
    old_orphan = _photo(tmp_path, "old.jpg")
    new_orphan = _photo(tmp_path, "new.jpg")
    await hass.services.async_call(
        DOMAIN,
        "add_refuel",
        {"liters": 10, "total_cost": 18, "image": _id("used.jpg")},
        blocking=True,
    )
    long_ago = time.time() - 2 * 86400
    for p in (used, old_orphan):
        os.utime(p, (long_ago, long_ago))

    midnight = dt_util.now().replace(hour=0, minute=0, second=5, microsecond=0) + timedelta(days=1)
    async_fire_time_changed(hass, midnight)
    await hass.async_block_till_done()
    assert used.exists()  # linked to an entry
    assert new_orphan.exists()  # younger than a day
    assert not old_orphan.exists()
    assert entry.runtime_data.data["log"][0]["image"] == _id("used.jpg")


# -------------------------------------------------------------- side-menu panel
def _panels(hass: HomeAssistant) -> dict:
    return hass.data.get("frontend_panels", {})


async def test_panel_in_side_menu_and_option_to_hide(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    panel = _panels(hass)["costi-auto"]
    assert panel.sidebar_title == "Costi Auto"
    assert panel.sidebar_icon == "mdi:car-electric"
    assert panel.require_admin is False

    hass.config_entries.async_update_entry(entry, options={**entry.data, "show_panel": False})
    await hass.async_block_till_done()
    assert "costi-auto" not in _panels(hass)

    hass.config_entries.async_update_entry(entry, options={**entry.data, "show_panel": True})
    await hass.async_block_till_done()
    assert "costi-auto" in _panels(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert "costi-auto" not in _panels(hass)


async def test_panel_files_are_served(hass: HomeAssistant, hass_client_no_auth) -> None:
    await _setup(hass)
    client = await hass_client_no_auth()
    res = await client.get("/car_costs_static/panel.js")
    assert res.status == 200
    assert "car-costs-panel" in await res.text()
