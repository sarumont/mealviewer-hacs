"""Diagnostics support for MealViewer."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import MealViewerConfigEntry
from .models import as_dict


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MealViewerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    window = coordinator.window
    return {
        "options": dict(entry.options),
        "window": [d.isoformat() for d in window] if window else None,
        "menu": as_dict(coordinator.data),
        "raw": entry.runtime_data.client.last_menu_payload,
    }
