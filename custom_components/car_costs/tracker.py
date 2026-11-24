"""Cost tracker: keeps the log and computes the comparison."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
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
    KIND_CHARGE,
    KIND_REFUEL,
    LOCATION_HOME,
    STORAGE_VERSION,
)

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


def empty_data() -> dict[str, Any]:
    return {
        "log": [],
        "home_kwh": 0.0,
        "home_cost": 0.0,
        "last_energy_reading": None,
        "last_odometer": None,
        "ref_km": 0.0,
        "ref_cost": 0.0,
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
    def _on_midnight(self, _now: datetime) -> None:
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
        self.data["home_kwh"] += delta
        self.data["home_cost"] += delta * self.electricity_price

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
            }
        )

    def delete(self, item_id: str) -> bool:
        before = len(self.data["log"])
        self.data["log"] = [e for e in self.data["log"] if e["id"] != item_id]
        if len(self.data["log"]) == before:
            return False
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
        )

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self.data["log"]))[:limit]


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
