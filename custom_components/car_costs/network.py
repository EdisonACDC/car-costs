"""The address of the phone web app."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url


def app_link(hass: HomeAssistant) -> dict[str, Any]:
    """Address of the phone web app: the external one (Nabu Casa / external_url) if there is one."""
    for external in (True, False):
        try:
            base = get_url(
                hass,
                allow_internal=not external,
                allow_external=external,
                allow_cloud=external,
                prefer_external=external,
            )
        except NoURLAvailableError:
            continue
        return {"url": f"{base.rstrip('/')}/car-costs", "external": external}
    return {"url": None, "external": False}
