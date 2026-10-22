"""Binary sensor platform for MealViewer."""

from __future__ import annotations

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import MealViewerConfigEntry, MealViewerCoordinator
from .entity import MealViewerEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealViewerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the school day sensor."""
    async_add_entities([MealViewerSchoolDaySensor(entry.runtime_data.coordinator)])


class MealViewerSchoolDaySensor(MealViewerEntity, BinarySensorEntity):
    """On when any meal is served today."""

    _attr_translation_key = "school_day"

    def __init__(self, coordinator: MealViewerCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "school_day")

    @property
    @override
    def is_on(self) -> bool:
        """Whether today has a menu."""
        day = self.coordinator.data.days.get(dt_util.now().date())
        return bool(day and day.is_school_day)
