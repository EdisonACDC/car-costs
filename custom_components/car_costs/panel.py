"""The "Costi Auto" panel in Home Assistant's side menu (no add-on, no second login)."""

from __future__ import annotations

from homeassistant.components import frontend, panel_custom
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import (
    CONF_SHOW_PANEL,
    DOMAIN,
    FRONTEND_URL,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    VERSION,
)

_FLAG = f"{DOMAIN}_panel"


def _wanted(hass: HomeAssistant, leaving: ConfigEntry | None) -> bool:
    """The panel is shown while at least one loaded car does not hide it."""
    return any(
        {**e.data, **e.options}.get(CONF_SHOW_PANEL, True)
        for e in hass.config_entries.async_entries(DOMAIN)
        if e is not leaving
        and e.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_IN_PROGRESS)
    )


async def async_sync_panel(hass: HomeAssistant, leaving: ConfigEntry | None = None) -> None:
    """Register or remove the side-menu panel so it matches the cars' options."""
    wanted = _wanted(hass, leaving)
    shown = hass.data.get(_FLAG, False)
    if wanted and not shown:
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name="car-costs-panel",
            frontend_url_path=PANEL_URL_PATH,
            module_url=f"{FRONTEND_URL}/panel.js?v={VERSION}",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=False,
            config={},
            embed_iframe=False,
        )
        hass.data[_FLAG] = True
    elif not wanted and shown:
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
        hass.data[_FLAG] = False
