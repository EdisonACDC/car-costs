"""Read a fuel or charging receipt from a photo with Home Assistant AI Task."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import KIND_CHARGE, KIND_REFUEL, LOCATION_PUBLIC, MEDIA_SUBDIR

_LOGGER = logging.getLogger(__name__)

INSTRUCTIONS = """You read a receipt photographed by a car owner.
It is either a FUEL receipt (petrol station: Super, Super E10, Super Plus,
Benzin, Diesel, litres/Liter/l) or an EV CHARGING receipt (kWh).
Receipts are usually German or Italian. Extract:
- kind: "refuel" for fuel, "charge" for electric charging
- liters: litres of fuel (fuel receipts only)
- kwh: energy charged in kWh (charging receipts only)
- total_cost: the total amount paid in EUR for fuel/energy only
  (exclude shop items such as coffee, car wash or snacks)
- price_per_unit: price per litre or per kWh in EUR
- date: purchase date as YYYY-MM-DD
- station: station or operator name and town, short
- fuel: product name (e.g. "Super E10", "Diesel")
Use a dot as decimal separator. If a value is not readable, leave it out.
Never invent values."""

STRUCTURE: dict[str, Any] = {
    "kind": {
        "description": "refuel or charge",
        "required": True,
        "selector": {"select": {"options": [KIND_REFUEL, KIND_CHARGE]}},
    },
    "liters": {
        "description": "Litres of fuel",
        "selector": {"number": {"min": 0, "max": 500, "step": 0.01, "mode": "box"}},
    },
    "kwh": {
        "description": "kWh charged",
        "selector": {"number": {"min": 0, "max": 500, "step": 0.001, "mode": "box"}},
    },
    "total_cost": {
        "description": "Total paid for fuel/energy in EUR",
        "selector": {"number": {"min": 0, "max": 2000, "step": 0.01, "mode": "box"}},
    },
    "price_per_unit": {
        "description": "EUR per litre or per kWh",
        "selector": {"number": {"min": 0, "max": 10, "step": 0.001, "mode": "box"}},
    },
    "date": {"description": "Date YYYY-MM-DD", "selector": {"text": {}}},
    "station": {"description": "Station name and town", "selector": {"text": {}}},
    "fuel": {"description": "Fuel product name", "selector": {"text": {}}},
}

_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def media_dir(hass: HomeAssistant) -> tuple[str, Path]:
    """Return (media source key, folder) where receipts are stored."""
    dirs = hass.config.media_dirs or {"local": hass.config.path("media")}
    key = "local" if "local" in dirs else next(iter(dirs))
    return key, Path(dirs[key]) / MEDIA_SUBDIR


MEDIA_PREFIX = "media-source://media_source/"
MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".pdf": "application/pdf",
}


def image_path(hass: HomeAssistant, media_id: Any) -> Path | None:
    """Local file of a stored receipt photo, only if inside <media>/car_costs."""
    if not isinstance(media_id, str) or not media_id.startswith(MEDIA_PREFIX):
        return None
    key, _, rel = media_id[len(MEDIA_PREFIX) :].partition("/")
    dirs = hass.config.media_dirs or {"local": hass.config.path("media")}
    if key not in dirs or not rel:
        return None
    folder = (Path(dirs[key]) / MEDIA_SUBDIR).resolve()
    candidate = (Path(dirs[key]) / unquote(rel)).resolve()
    if candidate.parent != folder:
        return None
    return candidate


async def async_save_image(
    hass: HomeAssistant, content: bytes, filename: str, entry_id: str
) -> tuple[str, str]:
    """Store the photo in the media folder; return (media id, mime type)."""
    key, folder = media_dir(hass)
    suffix = Path(filename or "receipt.jpg").suffix.lower() or ".jpg"
    if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"):
        suffix = ".jpg"
    name = _SAFE.sub(
        "_",
        f"{dt_util.now().strftime('%Y%m%d_%H%M%S')}_{entry_id[:6]}_{uuid.uuid4().hex[:6]}{suffix}",
    )

    def _write() -> None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(content)

    await hass.async_add_executor_job(_write)
    mime = {
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".pdf": "application/pdf",
    }.get(suffix, "image/jpeg")
    return f"media-source://media_source/{key}/{MEDIA_SUBDIR}/{name}", mime


async def async_read_receipt(
    hass: HomeAssistant,
    media_content_id: str,
    mime: str = "image/jpeg",
    ai_task_entity: str | None = None,
) -> dict[str, Any]:
    """Ask the AI Task entity to extract the receipt data."""
    if not hass.services.has_service("ai_task", "generate_data"):
        raise HomeAssistantError(
            "AI Task is not set up. Add an AI integration (OpenAI, Google "
            "Gemini, Anthropic, Ollama with a vision model…) and choose it in "
            "the Car Costs options."
        )
    payload: dict[str, Any] = {
        "task_name": "Car Costs receipt",
        "instructions": INSTRUCTIONS,
        "structure": STRUCTURE,
        "attachments": [{"media_content_id": media_content_id, "media_content_type": mime}],
    }
    if ai_task_entity:
        payload["entity_id"] = ai_task_entity
    response = await hass.services.async_call(
        "ai_task", "generate_data", payload, blocking=True, return_response=True
    )
    data = (response or {}).get("data") or {}
    if not isinstance(data, dict):
        raise HomeAssistantError("The AI did not return structured data")
    return normalise(data, media_content_id)


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(str(value).replace(",", ".")), 3)
    except (TypeError, ValueError):
        return None


def normalise(raw: dict[str, Any], media_content_id: str | None = None) -> dict[str, Any]:
    """Clean the AI answer and fill gaps that can be computed."""
    kind = raw.get("kind")
    liters = _num(raw.get("liters"))
    kwh = _num(raw.get("kwh"))
    if kind not in (KIND_REFUEL, KIND_CHARGE):
        kind = KIND_CHARGE if kwh and not liters else KIND_REFUEL
    total = _num(raw.get("total_cost"))
    unit = _num(raw.get("price_per_unit"))
    qty = liters if kind == KIND_REFUEL else kwh
    if total is None and qty and unit:
        total = round(qty * unit, 2)
    if qty is None and total and unit:
        qty = round(total / unit, 2)
    parsed = dt_util.parse_date(str(raw.get("date") or "")[:10])
    result: dict[str, Any] = {
        "kind": kind,
        "total_cost": None if total is None else round(total, 2),
        "price_per_unit": unit,
        "date": parsed.isoformat() if parsed else dt_util.now().date().isoformat(),
        "station": (raw.get("station") or None),
        "fuel": (raw.get("fuel") or None),
        "image": media_content_id,
    }
    if kind == KIND_REFUEL:
        result["liters"] = qty
    else:
        result["kwh"] = qty
        result["location"] = LOCATION_PUBLIC
    result["complete"] = bool(qty) and result["total_cost"] is not None
    return result
