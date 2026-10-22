"""Sensor platform for MealViewer: next menu per meal block."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .calendar import entree_summary
from .const import ENTREE_CATEGORY
from .coordinator import MealViewerConfigEntry, MealViewerCoordinator
from .entity import MealViewerEntity, async_add_block_entities
from .models import MealBlock, as_dict

PARALLEL_UPDATES = 0

MAX_STATE_LENGTH = 255


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealViewerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    async_add_block_entities(
        entry,
        async_add_entities,
        lambda coordinator, slug, name: [
            MealViewerNextMenuSensor(coordinator, slug, name)
        ],
    )


class MealViewerNextMenuSensor(MealViewerEntity, SensorEntity):
    """Entrees for the next serving of a meal block, with full menu attributes."""

    _attr_translation_key = "next_menu"
    # The full menu easily exceeds the recorder's attribute size limit.
    _unrecorded_attributes = frozenset({"items"})

    def __init__(
        self, coordinator: MealViewerCoordinator, slug: str, name: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"{slug}_next")
        self._slug = slug
        self._attr_translation_placeholders = {"block": name}

    @property
    def _block(self) -> MealBlock | None:
        return self.coordinator.data.next_block(
            self._slug, self.coordinator.target_date()
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Comma-joined entrees."""
        if not (block := self._block):
            return None
        return entree_summary(block)[:MAX_STATE_LENGTH]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Date and full structured menu."""
        if not (block := self._block):
            return {}
        return {
            "date": block.date.isoformat(),
            "block": block.name,
            "entrees": [i.display_name for i in block.items_in(ENTREE_CATEGORY)],
            "items": [as_dict(i) for i in block.items],
        }
