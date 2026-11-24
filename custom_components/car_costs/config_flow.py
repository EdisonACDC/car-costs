"""Config flow for Car Costs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_ELECTRICITY_PRICE,
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_EXTRA_INVESTMENT,
    CONF_HOME_ENERGY_ENTITY,
    CONF_NAME,
    CONF_NEW_INSURANCE,
    CONF_NEW_MAINTENANCE,
    CONF_NEW_TAX,
    CONF_ODOMETER_ENTITY,
    CONF_OLD_CAR_SALE_PRICE,
    CONF_PURCHASE_PRICE,
    CONF_REF_CONSUMPTION,
    CONF_REF_FUEL,
    CONF_REF_FUEL_PRICE,
    CONF_REF_FUEL_PRICE_ENTITY,
    CONF_REF_INSURANCE,
    CONF_REF_MAINTENANCE,
    CONF_REF_NAME,
    CONF_REF_TAX,
    CONF_START_DATE,
    CONF_START_ODOMETER,
    DEFAULTS,
    DOMAIN,
    FUEL_TYPES,
)


def _euro(maximum: float = 500000, step: float = 1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="€",
        )
    )


def _number(unit: str, maximum: float, step: float) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _sensor() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "input_number", "number"]))


def _opt(key: str, values: dict[str, Any]) -> vol.Optional:
    """Optional field pre-filled with the current value, if any."""
    if values.get(key) not in (None, ""):
        return vol.Optional(key, description={"suggested_value": values[key]})
    return vol.Optional(key)


def _req(key: str, values: dict[str, Any]) -> vol.Required:
    default = values.get(key, DEFAULTS.get(key))
    return vol.Required(key, default=default) if default is not None else vol.Required(key)


def car_schema(v: dict[str, Any]) -> dict:
    return {
        _req(CONF_NAME, v): selector.TextSelector(),
        _req(CONF_PURCHASE_PRICE, v): _euro(),
        _req(CONF_EXTRA_INVESTMENT, v): _euro(),
        _req(CONF_START_DATE, v): selector.DateSelector(),
        _req(CONF_START_ODOMETER, v): _number("km", 2000000, 1),
        _opt(CONF_ODOMETER_ENTITY, v): _sensor(),
    }


def energy_schema(v: dict[str, Any]) -> dict:
    return {
        _req(CONF_ELECTRICITY_PRICE, v): _number("€/kWh", 5, 0.001),
        _opt(CONF_ELECTRICITY_PRICE_ENTITY, v): _sensor(),
        _opt(CONF_HOME_ENERGY_ENTITY, v): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="energy")
        ),
        _opt(CONF_AI_TASK_ENTITY, v): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="ai_task")
        ),
    }


def reference_schema(v: dict[str, Any]) -> dict:
    return {
        _req(CONF_REF_NAME, v): selector.TextSelector(),
        _req(CONF_REF_FUEL, v): selector.SelectSelector(
            selector.SelectSelectorConfig(options=FUEL_TYPES, translation_key="fuel")
        ),
        _req(CONF_REF_CONSUMPTION, v): _number("L/100 km", 30, 0.1),
        _req(CONF_REF_FUEL_PRICE, v): _number("€/L", 5, 0.001),
        _opt(CONF_REF_FUEL_PRICE_ENTITY, v): _sensor(),
        _req(CONF_OLD_CAR_SALE_PRICE, v): _euro(),
    }


def fixed_schema(v: dict[str, Any]) -> dict:
    return {
        _req(key, v): _euro(20000)
        for key in (
            CONF_NEW_TAX,
            CONF_NEW_INSURANCE,
            CONF_NEW_MAINTENANCE,
            CONF_REF_TAX,
            CONF_REF_INSURANCE,
            CONF_REF_MAINTENANCE,
        )
    }


class CarCostsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Four short steps: car, energy, old car, yearly costs."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {CONF_START_DATE: dt_util.now().date().isoformat()}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_energy()
        return self.async_show_form(step_id="user", data_schema=vol.Schema(car_schema(self._data)))

    async def async_step_energy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_reference()
        return self.async_show_form(step_id="energy", data_schema=vol.Schema(energy_schema(self._data)))

    async def async_step_reference(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_fixed()
        return self.async_show_form(step_id="reference", data_schema=vol.Schema(reference_schema(self._data)))

    async def async_step_fixed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return self.async_show_form(step_id="fixed", data_schema=vol.Schema(fixed_schema(self._data)))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return CarCostsOptionsFlow()


class CarCostsOptionsFlow(OptionsFlow):
    """Same four steps, pre-filled; empty optional fields clear the value."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options, **self._data}

    def _store(self, user_input: dict[str, Any], schema: dict) -> None:
        for key in schema:
            name = str(key)
            self._data[name] = user_input.get(name)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        schema = car_schema(self._current())
        if user_input is not None:
            self._store(user_input, schema)
            return await self.async_step_energy()
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))

    async def async_step_energy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        schema = energy_schema(self._current())
        if user_input is not None:
            self._store(user_input, schema)
            return await self.async_step_reference()
        return self.async_show_form(step_id="energy", data_schema=vol.Schema(schema))

    async def async_step_reference(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        schema = reference_schema(self._current())
        if user_input is not None:
            self._store(user_input, schema)
            return await self.async_step_fixed()
        return self.async_show_form(step_id="reference", data_schema=vol.Schema(schema))

    async def async_step_fixed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        schema = fixed_schema(self._current())
        if user_input is not None:
            self._store(user_input, schema)
            return self.async_create_entry(data={**self.config_entry.options, **self._data})
        return self.async_show_form(step_id="fixed", data_schema=vol.Schema(schema))
