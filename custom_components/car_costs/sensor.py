"""Sensors for Car Costs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfLength, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CarCostsConfigEntry
from .const import DOMAIN, VERSION
from .tracker import CarCostTracker, Summary

EUR = "EUR"


@dataclass(frozen=True, kw_only=True)
class CarCostSensorDescription(SensorEntityDescription):
    value: Callable[[Summary], Any]


def _money(key: str, value: Callable[[Summary], Any], icon: str, total: bool = False) -> CarCostSensorDescription:
    return CarCostSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=EUR,
        state_class=SensorStateClass.TOTAL if total else None,
        suggested_display_precision=2,
        icon=icon,
        value=value,
    )


SENSORS: tuple[CarCostSensorDescription, ...] = (
    CarCostSensorDescription(
        key="km_driven",
        translation_key="km_driven",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        icon="mdi:counter",
        value=lambda s: s.km_driven,
    ),
    CarCostSensorDescription(
        key="fuel_liters",
        translation_key="fuel_liters",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        icon="mdi:gas-station",
        value=lambda s: s.fuel_liters,
    ),
    CarCostSensorDescription(
        key="electricity_kwh",
        translation_key="electricity_kwh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        icon="mdi:ev-station",
        value=lambda s: s.electricity_kwh,
    ),
    _money("fuel_cost", lambda s: s.fuel_cost, "mdi:gas-station", True),
    _money("electricity_cost", lambda s: s.electricity_cost, "mdi:lightning-bolt", True),
    _money("energy_cost", lambda s: s.energy_cost, "mdi:cash", True),
    _money("reference_cost", lambda s: s.reference_cost, "mdi:car-side", True),
    _money("energy_savings", lambda s: s.energy_savings, "mdi:piggy-bank-outline", True),
    _money("fixed_cost_savings", lambda s: s.fixed_cost_savings, "mdi:file-document-outline", True),
    _money("total_savings", lambda s: s.total_savings, "mdi:piggy-bank", True),
    _money("savings_per_month", lambda s: s.savings_per_month, "mdi:calendar-month"),
    _money("investment", lambda s: s.investment, "mdi:car-key"),
    CarCostSensorDescription(
        key="cost_per_100km",
        translation_key="cost_per_100km",
        native_unit_of_measurement="EUR/100 km",
        suggested_display_precision=2,
        icon="mdi:speedometer",
        value=lambda s: s.cost_per_100km,
    ),
    CarCostSensorDescription(
        key="reference_cost_per_100km",
        translation_key="reference_cost_per_100km",
        native_unit_of_measurement="EUR/100 km",
        suggested_display_precision=2,
        icon="mdi:speedometer-slow",
        value=lambda s: s.reference_cost_per_100km,
    ),
    CarCostSensorDescription(
        key="avg_fuel_consumption",
        translation_key="avg_fuel_consumption",
        native_unit_of_measurement="L/100 km",
        suggested_display_precision=1,
        icon="mdi:fuel",
        value=lambda s: s.avg_fuel_consumption,
    ),
    CarCostSensorDescription(
        key="amortization",
        translation_key="amortization",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        icon="mdi:progress-check",
        value=lambda s: s.amortization,
    ),
    CarCostSensorDescription(
        key="break_even_date",
        translation_key="break_even_date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:flag-checkered",
        value=lambda s: s.break_even_date,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CarCostsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    tracker = entry.runtime_data
    async_add_entities(CarCostSensor(tracker, d) for d in SENSORS)


class CarCostSensor(SensorEntity):
    """A computed Car Costs value."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: CarCostSensorDescription

    def __init__(self, tracker: CarCostTracker, description: CarCostSensorDescription) -> None:
        self.tracker = tracker
        self.entity_description = description
        entry = tracker.entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Car Costs",
            model=f"vs {tracker.opt('ref_name')}",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.tracker.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.tracker.summary())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        key = self.entity_description.key
        if key == "total_savings":
            s = self.tracker.summary()
            return {
                "config_entry_id": self.tracker.entry.entry_id,
                "days": s.days,
                "investment": s.investment,
                "energy_savings": s.energy_savings,
                "fixed_cost_savings": s.fixed_cost_savings,
                "reference_car": self.tracker.opt("ref_name"),
            }
        if key == "reference_cost":
            return {
                "fuel_price": self.tracker.ref_fuel_price,
                "consumption_l_100km": self.tracker.opt("ref_consumption"),
            }
        if key == "electricity_cost":
            s = self.tracker.summary()
            return {
                "home_kwh": s.home_kwh,
                "electricity_price": self.tracker.electricity_price,
            }
        return None
