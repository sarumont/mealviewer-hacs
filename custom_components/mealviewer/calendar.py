"""Calendar platform for MealViewer: one calendar per meal block."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import MealViewerError
from .const import DOMAIN, ENTREE_CATEGORY
from .coordinator import MealViewerConfigEntry, MealViewerCoordinator
from .entity import MealViewerEntity, async_add_block_entities
from .models import FoodItem, MealBlock

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealViewerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up calendars."""
    async_add_block_entities(
        entry,
        async_add_entities,
        lambda coordinator, slug, name: [
            MealViewerCalendarEntity(coordinator, slug, name)
        ],
    )


def entree_summary(block: MealBlock) -> str:
    """Comma-joined entree names, falling back to the block name."""
    entrees = block.items_in(ENTREE_CATEGORY)
    return ", ".join(i.display_name for i in entrees) or block.name


def _describe_item(item: FoodItem) -> str:
    line = f"- {item.display_name}"
    if item.name_line_2:
        line += f" {item.name_line_2}"
    macros = [
        f"{n.value:g} {n.unit or ''}".strip() + f" {n.name.lower()}"
        for key in ("calories", "protein", "total_carbs", "total_fat", "sugars")
        if (n := item.nutrients.get(key)) and n.valid and n.value is not None
    ]
    if macros:
        line += f" ({' · '.join(macros)})"
    if item.allergens:
        line += f" [{', '.join(a.name for a in item.allergens)}]"
    return line


def describe_block(block: MealBlock) -> str:
    """Full menu grouped by category."""
    if block.blacked_out:
        return block.no_schedule_text or "Not served"
    sections: dict[str, list[str]] = {}
    for item in block.items:
        sections.setdefault(item.category.title(), []).append(_describe_item(item))
    return "\n\n".join(
        f"{category}\n" + "\n".join(lines) for category, lines in sections.items()
    )


def block_event(block: MealBlock) -> CalendarEvent:
    """All-day event for a meal block."""
    return CalendarEvent(
        start=block.date,
        end=block.date + timedelta(days=1),
        summary=entree_summary(block),
        description=describe_block(block),
        uid=f"{block.id}_{block.date.isoformat()}",
    )


class MealViewerCalendarEntity(MealViewerEntity, CalendarEntity):
    """Menu calendar for one meal block."""

    _attr_translation_key = "menu"

    def __init__(
        self, coordinator: MealViewerCoordinator, slug: str, name: str
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator, f"{slug}_calendar")
        self._slug = slug
        self._attr_translation_placeholders = {"block": name}

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Today's or the next upcoming menu."""
        block = self.coordinator.data.next_block(self._slug, dt_util.now().date())
        return block_event(block) if block else None

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Menus within a time range."""
        try:
            menu = await self.coordinator.async_get_range(
                start_date.date(), end_date.date()
            )
        except MealViewerError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err
        return [
            block_event(block)
            for day in menu.days.values()
            if (block := day.block(self._slug)) and not block.blacked_out
        ]
