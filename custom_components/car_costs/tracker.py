"""Cost tracker: keeps the log and computes the comparison."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from pathlib import Path
from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ELECTRICITY_PRICE,
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_EV_CONSUMPTION,
    CONF_EXTRA_INVESTMENT,
    CONF_HOME_ENERGY_ENTITY,
    CONF_NEW_INSURANCE,
    CONF_NEW_MAINTENANCE,
    CONF_NEW_TAX,
    CONF_ODOMETER_ENTITY,
    CONF_OLD_CAR_SALE_PRICE,
    CONF_PURCHASE_PRICE,
    CONF_REF_CONSUMPTION,
    CONF_REF_FUEL_PRICE,
    CONF_REF_FUEL_PRICE_ENTITY,
    CONF_REF_INSURANCE,
    CONF_REF_MAINTENANCE,
    CONF_REF_TAX,
    CONF_START_DATE,
    CONF_START_ODOMETER,
    DEFAULTS,
    DOMAIN,
    EVENT_UPDATED,
    HISTORY_MAX_DAYS,
    KIND_CHARGE,
    KIND_REFUEL,
    LOCATION_HOME,
    STORAGE_VERSION,
)
from .receipt import image_path

_LOGGER = logging.getLogger(__name__)

# Below this many days the daily savings rate is too noisy for a forecast.
MIN_DAYS_FOR_FORECAST = 7


def _to_float(value: Any) -> float | None:
    if value in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


@dataclass
class Summary:
    """Computed values shown by the sensors."""

    days: int
    km_driven: float
    fuel_liters: float
    fuel_cost: float
    electricity_kwh: float
    electricity_cost: float
    home_kwh: float
    energy_cost: float
    cost_per_100km: float | None
    avg_fuel_consumption: float | None
    reference_cost: float
    reference_cost_per_100km: float | None
    energy_savings: float
    fixed_cost_savings: float
    total_savings: float
    investment: float
    amortization: float | None
    break_even_date: date | None
    savings_per_month: float | None
    ev_share_pct: float | None = None


def empty_data() -> dict[str, Any]:
    return {
        "log": [],
        "home_kwh": 0.0,
        "home_cost": 0.0,
        "last_energy_reading": None,
        "last_odometer": None,
        "ref_km": 0.0,
        "ref_cost": 0.0,
        "history": [],
        "home_daily": {},
    }


class CarCostTracker:
    """One tracked car compared with a reference car."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.data: dict[str, Any] = empty_data()
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []

    # ------------------------------------------------------------------ config
    def opt(self, key: str) -> Any:
        """Value from options, falling back to data and defaults."""
        if key in self.entry.options:
            return self.entry.options[key]
        if key in self.entry.data:
            return self.entry.data[key]
        return DEFAULTS.get(key)

    def _num(self, key: str) -> float:
        return _to_float(self.opt(key)) or 0.0

    def _entity_value(self, entity_key: str) -> float | None:
        entity_id = self.opt(entity_key)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return _to_float(state.state) if state else None

    @property
    def electricity_price(self) -> float:
        value = self._entity_value(CONF_ELECTRICITY_PRICE_ENTITY)
        return value if value is not None else self._num(CONF_ELECTRICITY_PRICE)

    @property
    def ref_fuel_price(self) -> float:
        value = self._entity_value(CONF_REF_FUEL_PRICE_ENTITY)
        return value if value is not None else self._num(CONF_REF_FUEL_PRICE)

    @property
    def start_date(self) -> date:
        raw = self.opt(CONF_START_DATE)
        parsed = dt_util.parse_date(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, date):
            return parsed
        return dt_util.now().date()

    @property
    def start_odometer(self) -> float:
        configured = self._num(CONF_START_ODOMETER)
        if configured > 0:
            return configured
        return self.data.get("auto_start_odometer") or 0.0

    # ----------------------------------------------------------------- storage
    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.data = {**empty_data(), **stored}
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, self._tracked_entities(), self._on_state_change
            )
        )
        # Days-based values (fixed costs, forecast) move once a day.
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._on_midnight, hour=0, minute=0, second=5
            )
        )
        # Pick up values that changed while HA was down.
        self._sync_odometer()
        self._sync_home_energy()
        if not self.data.get("history"):
            self.snapshot()  # first start: the first point of the series
        self._save()

    def _tracked_entities(self) -> list[str]:
        return [
            e
            for e in (
                self.opt(CONF_ODOMETER_ENTITY),
                self.opt(CONF_HOME_ENERGY_ENTITY),
                self.opt(CONF_ELECTRICITY_PRICE_ENTITY),
                self.opt(CONF_REF_FUEL_PRICE_ENTITY),
            )
            if e
        ]

    async def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self.data)

    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 2)

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(update)

        def remove() -> None:
            self._listeners.remove(update)

        return remove

    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
        self.hass.bus.async_fire(EVENT_UPDATED, {"config_entry_id": self.entry.entry_id})

    # ------------------------------------------------------------ live sensors
    @callback
    def _on_midnight(self, now: datetime) -> None:
        # Close the day that just ended: one point per day for the charts.
        self.snapshot((now - timedelta(days=1)).date())
        self._save()
        self._notify()

    @callback
    def _on_state_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        if entity_id == self.opt(CONF_ODOMETER_ENTITY):
            self._sync_odometer()
        elif entity_id == self.opt(CONF_HOME_ENERGY_ENTITY):
            self._sync_home_energy()
        self._save()
        self._notify()

    def _sync_odometer(self) -> None:
        value = self._entity_value(CONF_ODOMETER_ENTITY)
        if value is not None and value > 0:
            if (
                self._num(CONF_START_ODOMETER) <= 0
                and self.data.get("auto_start_odometer") is None
            ):
                # No start km configured: the first reading is the baseline.
                self.data["auto_start_odometer"] = value
            last = self.data.get("last_odometer")
            if last is None or value >= last:
                self.data["last_odometer"] = value
        self._accrue_reference()

    def _sync_home_energy(self) -> None:
        reading = self._entity_value(CONF_HOME_ENERGY_ENTITY)
        if reading is None:
            return
        last = self.data.get("last_energy_reading")
        self.data["last_energy_reading"] = reading
        if last is None:
            return  # first reading is the baseline
        delta = reading - last if reading >= last else reading  # meter reset
        if delta <= 0 or delta > 100:  # >100 kWh in one step is a glitch
            return
        cost = delta * self.electricity_price
        self.data["home_kwh"] += delta
        self.data["home_cost"] += cost
        day = self.data.setdefault("home_daily", {}).setdefault(
            dt_util.now().date().isoformat(), {"kwh": 0.0, "cost": 0.0}
        )
        day["kwh"] = round(day["kwh"] + delta, 4)
        day["cost"] = round(day["cost"] + cost, 4)

    # ------------------------------------------------------------- km / Passat
    def current_odometer(self) -> float | None:
        values = [self.data.get("last_odometer")]
        values += [e.get("odometer") for e in self.data["log"]]
        values = [v for v in values if isinstance(v, (int, float)) and v > 0]
        return max(values) if values else None

    def km_driven(self) -> float:
        odo = self.current_odometer()
        if odo is None:
            return 0.0
        return max(0.0, odo - self.start_odometer)

    def _accrue_reference(self) -> None:
        """Add the reference car's fuel cost for the new km at today's price."""
        km = self.km_driven()
        done = self.data.get("ref_km", 0.0)
        litres_per_km = self._num(CONF_REF_CONSUMPTION) / 100
        if km < done:  # correction (entry deleted or start odometer changed)
            self.data["ref_km"] = km
            self.data["ref_cost"] = km * litres_per_km * self.ref_fuel_price
            return
        delta = km - done
        if delta > 0:
            self.data["ref_km"] = km
            self.data["ref_cost"] = (
                self.data.get("ref_cost", 0.0)
                + delta * litres_per_km * self.ref_fuel_price
            )

    @callback
    def async_options_changed(self) -> None:
        """Recompute derived values after the options changed."""
        km = self.km_driven()
        self.data["ref_km"] = km
        self.data["ref_cost"] = (
            km * self._num(CONF_REF_CONSUMPTION) / 100 * self.ref_fuel_price
        )
        self._save()
        self._notify()

    # ------------------------------------------------------------------- log
    def _add(self, item: dict[str, Any]) -> dict[str, Any]:
        item["id"] = uuid.uuid4().hex[:12]
        item.setdefault("date", dt_util.now().date().isoformat())
        item["created"] = dt_util.utcnow().isoformat()
        self.data["log"].append(item)
        self.data["log"].sort(key=lambda e: (e.get("date") or "", e["created"]))
        self._accrue_reference()
        self._save()
        self._notify()
        return item

    def add_refuel(
        self,
        liters: float,
        total_cost: float,
        *,
        odometer: float | None = None,
        day: str | None = None,
        station: str | None = None,
        note: str | None = None,
        source: str = "manual",
        image: str | None = None,
    ) -> dict[str, Any]:
        return self._add(
            {
                "kind": KIND_REFUEL,
                "liters": round(float(liters), 2),
                "total_cost": round(float(total_cost), 2),
                "odometer": odometer,
                "date": day or dt_util.now().date().isoformat(),
                "station": station,
                "note": note,
                "source": source,
                "image": image,
            }
        )

    def add_charge(
        self,
        kwh: float,
        total_cost: float | None = None,
        *,
        location: str = "public",
        odometer: float | None = None,
        day: str | None = None,
        station: str | None = None,
        note: str | None = None,
        source: str = "manual",
        image: str | None = None,
    ) -> dict[str, Any]:
        if total_cost is None:
            total_cost = float(kwh) * self.electricity_price
        return self._add(
            {
                "kind": KIND_CHARGE,
                "kwh": round(float(kwh), 2),
                "total_cost": round(float(total_cost), 2),
                "location": location,
                "odometer": odometer,
                "date": day or dt_util.now().date().isoformat(),
                "station": station,
                "note": note,
                "source": source,
                "image": image,
            }
        )

    def update(self, item_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Change an entry. Fields that do not fit its kind are ignored."""
        item = next((e for e in self.data["log"] if e["id"] == item_id), None)
        if item is None:
            return None
        allowed = set(EDITABLE_COMMON) | (
            set(EDITABLE_REFUEL) if item["kind"] == KIND_REFUEL else set(EDITABLE_CHARGE)
        )
        old_image = item.get("image")
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in ("liters", "kwh", "total_cost"):
                if value is None:
                    continue
                value = round(float(value), 2)
            elif key == "date":
                value = parse_day(value) or item.get("date")
            item[key] = value
        self.data["log"].sort(key=lambda e: (e.get("date") or "", e["created"]))
        if old_image and old_image != item.get("image"):
            self._remove_image(old_image, keep_for=item_id)
        self._accrue_reference()
        self._save()
        self._notify()
        return item

    def _remove_image(self, media_id: str, keep_for: str | None = None) -> None:
        """Delete a photo, unless another entry still uses it."""
        if any(
            e.get("image") == media_id and e["id"] != keep_for for e in self.data["log"]
        ):
            return
        path = image_path(self.hass, media_id)
        if path is not None:
            self.hass.async_create_task(self._async_unlink(path))

    async def _async_unlink(self, path: Path) -> None:
        await self.hass.async_add_executor_job(_unlink, path)

    def delete(self, item_id: str) -> bool:
        item = next((e for e in self.data["log"] if e["id"] == item_id), None)
        if item is None:
            return False
        self.data["log"] = [e for e in self.data["log"] if e["id"] != item_id]
        if item.get("image"):
            self._remove_image(item["image"])
        self._accrue_reference()
        self._save()
        self._notify()
        return True

    # --------------------------------------------------------------- summary
    def summary(self, today: date | None = None) -> Summary:
        today = today or dt_util.now().date()
        log = self.data["log"]
        refuels = [e for e in log if e["kind"] == KIND_REFUEL]
        charges = [e for e in log if e["kind"] == KIND_CHARGE]

        days = max(0, (today - self.start_date).days)
        km = self.km_driven()

        fuel_liters = sum(e["liters"] for e in refuels)
        fuel_cost = sum(e["total_cost"] for e in refuels)
        home_kwh = self.data.get("home_kwh", 0.0)
        el_kwh = sum(e["kwh"] for e in charges) + home_kwh
        el_cost = sum(e["total_cost"] for e in charges) + self.data.get(
            "home_cost", 0.0
        )
        energy_cost = fuel_cost + el_cost
        ref_cost = self.data.get("ref_cost", 0.0)

        new_fixed = sum(
            self._num(k) for k in (CONF_NEW_TAX, CONF_NEW_INSURANCE, CONF_NEW_MAINTENANCE)
        )
        ref_fixed = sum(
            self._num(k) for k in (CONF_REF_TAX, CONF_REF_INSURANCE, CONF_REF_MAINTENANCE)
        )
        fixed_savings = (ref_fixed - new_fixed) * days / 365

        energy_savings = ref_cost - energy_cost
        total_savings = energy_savings + fixed_savings
        investment = (
            self._num(CONF_PURCHASE_PRICE)
            + self._num(CONF_EXTRA_INVESTMENT)
            - self._num(CONF_OLD_CAR_SALE_PRICE)
        )
        amortization = total_savings / investment * 100 if investment > 0 else None

        break_even: date | None = None
        per_month: float | None = None
        if days >= MIN_DAYS_FOR_FORECAST:
            per_day = total_savings / days
            per_month = per_day * 30.44
            remaining = investment - total_savings
            if investment > 0 and remaining <= 0:
                break_even = today
            elif investment > 0 and per_day > 0:
                days_left = remaining / per_day
                if days_left < 365 * 100:
                    break_even = today + timedelta(days=round(days_left))

        ev_share: float | None = None
        ev_consumption = _to_float(self.opt(CONF_EV_CONSUMPTION))
        if ev_consumption and ev_consumption > 0 and km >= 1:
            ev_share = min(100.0, el_kwh / ev_consumption * 100 / km * 100)

        def per100(cost: float) -> float | None:
            return cost / km * 100 if km >= 1 else None

        return Summary(
            days=days,
            km_driven=round(km, 1),
            fuel_liters=round(fuel_liters, 2),
            fuel_cost=round(fuel_cost, 2),
            electricity_kwh=round(el_kwh, 2),
            electricity_cost=round(el_cost, 2),
            home_kwh=round(home_kwh, 2),
            energy_cost=round(energy_cost, 2),
            cost_per_100km=_round(per100(energy_cost)),
            avg_fuel_consumption=_round(fuel_liters / km * 100 if km >= 50 else None),
            reference_cost=round(ref_cost, 2),
            reference_cost_per_100km=_round(per100(ref_cost)),
            energy_savings=round(energy_savings, 2),
            fixed_cost_savings=round(fixed_savings, 2),
            total_savings=round(total_savings, 2),
            investment=round(investment, 2),
            amortization=_round(amortization),
            break_even_date=break_even,
            savings_per_month=_round(per_month),
            ev_share_pct=_round(ev_share, 1),
        )

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self.data["log"]))[:limit]

    # --------------------------------------------------------------- history
    def _point(self, day: date) -> dict[str, Any]:
        s = self.summary(day)
        return {
            "date": day.isoformat(),
            "km": s.km_driven,
            "energy_cost": s.energy_cost,
            "reference_cost": s.reference_cost,
            "total_savings": s.total_savings,
            "home_kwh": s.home_kwh,
            "home_cost": round(self.data.get("home_cost", 0.0), 2),
        }

    def snapshot(self, day: date | None = None) -> dict[str, Any]:
        """Store (or replace) the totals of one day; at most one point per day."""
        today = dt_util.now().date()
        point = self._point(day or today)
        history = [p for p in self.data.setdefault("history", []) if p["date"] != point["date"]]
        history.append(point)
        history.sort(key=lambda p: p["date"])
        limit = (today - timedelta(days=HISTORY_MAX_DAYS)).isoformat()
        self.data["history"] = [p for p in history if p["date"] >= limit]
        return point

    def history(self, months: int = 0) -> dict[str, Any]:
        """Monthly aggregates from the log plus the daily series.

        months=0 means everything. The daily series ends with a live point for
        today, which is not stored.
        """
        today = dt_util.now().date()
        live = self._point(today)
        daily = [p for p in self.data.get("history", []) if p["date"] != live["date"]]
        daily.append(live)

        buckets: dict[str, dict[str, float]] = {}

        def bucket(day: str) -> dict[str, float]:
            return buckets.setdefault(
                day[:7],
                {
                    "fuel_cost": 0.0, "fuel_liters": 0.0,
                    "public_cost": 0.0, "public_kwh": 0.0,
                    "home_cost": 0.0, "home_kwh": 0.0,
                },
            )

        for e in self.data["log"]:
            b = bucket(e.get("date") or today.isoformat())
            if e["kind"] == KIND_REFUEL:
                b["fuel_cost"] += e["total_cost"]
                b["fuel_liters"] += e["liters"]
            elif e.get("location") == LOCATION_HOME:
                b["home_cost"] += e["total_cost"]
                b["home_kwh"] += e["kwh"]
            else:
                b["public_cost"] += e["total_cost"]
                b["public_kwh"] += e["kwh"]
        for day, v in self.data.get("home_daily", {}).items():
            b = bucket(day)
            b["home_cost"] += v["cost"]
            b["home_kwh"] += v["kwh"]
        bucket(today.isoformat())

        first = min(min(buckets), daily[0]["date"][:7])
        names = _month_range(first, today.isoformat()[:7])
        if months > 0:
            names = names[-months:]

        out = []
        for name in names:
            b = bucket(name + "-01")
            before = [p for p in daily if p["date"][:7] < name]
            upto = [p for p in daily if p["date"][:7] <= name]
            ref_start = before[-1]["reference_cost"] if before else 0.0
            ref_end = upto[-1]["reference_cost"] if upto else 0.0
            energy = b["fuel_cost"] + b["public_cost"] + b["home_cost"]
            out.append(
                {
                    "month": name,
                    **{k: round(v, 2) for k, v in b.items()},
                    "energy_cost": round(energy, 2),
                    "reference_cost": round(max(0.0, ref_end - ref_start), 2),
                }
            )
        if months > 0 and out:
            start = out[0]["month"] + "-01"
            daily = [p for p in daily if p["date"] >= start]
        home_daily = [
            {"date": day, "kwh": round(v["kwh"], 2), "cost": round(v["cost"], 2)}
            for day, v in sorted(self.data.get("home_daily", {}).items())
            if months <= 0 or not out or day >= out[0]["month"] + "-01"
        ]
        return {
            "months": out,
            "daily": daily,
            "home_daily": home_daily,
            "investment": self.summary(today).investment,
        }


EDITABLE_COMMON = ("total_cost", "odometer", "date", "station", "note", "image")
EDITABLE_REFUEL = ("liters",)
EDITABLE_CHARGE = ("kwh", "location")


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as err:
        _LOGGER.warning("Could not delete %s: %s", path, err)


def _month_range(first: str, last: str) -> list[str]:
    y, m = int(first[:4]), int(first[5:7])
    ly, lm = int(last[:4]), int(last[5:7])
    names = []
    while (y, m) <= (ly, lm):
        names.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return names


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def parse_day(value: Any) -> str | None:
    """Normalise a date/datetime/string to ISO date."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = dt_util.parse_date(str(value)[:10])
    return parsed.isoformat() if parsed else None


__all__ = ["CarCostTracker", "LOCATION_HOME", "Summary", "parse_day"]
