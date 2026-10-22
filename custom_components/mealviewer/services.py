"""Services for the MealViewer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util import dt as dt_util
import probatio

from .api import MealViewerError
from .const import (
    ATTR_BLOCKS,
    ATTR_CATEGORIES,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END_DATE,
    ATTR_START_DATE,
    DOMAIN,
)
from .coordinator import MealViewerConfigEntry
from .models import MealBlock, MenuDay, as_dict, slugify

SERVICE_GET_MENU = "get_menu"
SERVICE_GET_MENU_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Optional(ATTR_START_DATE): cv.date,
        probatio.Optional(ATTR_END_DATE): cv.date,
        probatio.Optional(ATTR_BLOCKS): [str],
        probatio.Optional(ATTR_CATEGORIES): [str],
    }
)


def _block_dict(block: MealBlock, categories: set[str] | None) -> dict[str, Any]:
    data = as_dict(block)
    if categories is not None:
        for line in data["lines"]:
            line["items"] = [
                i for i in line["items"] if i["category"].upper() in categories
            ]
    return data


def _day_dict(
    day: MenuDay, blocks: set[str] | None, categories: set[str] | None
) -> dict[str, Any]:
    return {
        "date": day.date.isoformat(),
        "week_day_name": day.week_day_name,
        "is_school_day": day.is_school_day,
        "blocks": [
            _block_dict(b, categories)
            for b in day.blocks
            if blocks is None or b.slug in blocks
        ],
    }


async def _async_get_menu(call: ServiceCall) -> ServiceResponse:
    """Return the full menu for a date range."""
    entry: MealViewerConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    today = dt_util.now().date()
    start = call.data.get(ATTR_START_DATE, today)
    end = call.data.get(ATTR_END_DATE, start)
    if end < start:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="end_date_before_start_date"
        )
    blocks = (
        {slugify(b) for b in call.data[ATTR_BLOCKS]}
        if ATTR_BLOCKS in call.data
        else None
    )
    categories = (
        {c.upper() for c in call.data[ATTR_CATEGORIES]}
        if ATTR_CATEGORIES in call.data
        else None
    )
    try:
        menu = await entry.runtime_data.coordinator.async_get_range(start, end)
    except MealViewerError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err
    return {
        "school": as_dict(menu.school),
        "info": as_dict(menu.info),
        "days": [
            _day_dict(menu.days[d], blocks, categories) for d in sorted(menu.days)
        ],
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MENU,
        _async_get_menu,
        schema=SERVICE_GET_MENU_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
