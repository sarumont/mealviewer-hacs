"""The MealViewer integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MealViewerClient
from .const import CONF_SCHOOL, DOMAIN
from .coordinator import MealViewerConfigEntry, MealViewerCoordinator, MealViewerData
from .services import async_setup_services

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MealViewer component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MealViewerConfigEntry) -> bool:
    """Set up MealViewer from a config entry."""
    client = MealViewerClient(async_get_clientsession(hass), entry.data[CONF_SCHOOL])
    coordinator = MealViewerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    coordinator.async_setup_timers()

    entry.runtime_data = MealViewerData(client, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MealViewerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
