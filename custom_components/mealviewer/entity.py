"""Base entity for MealViewer."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MealViewerConfigEntry, MealViewerCoordinator


class MealViewerEntity(CoordinatorEntity[MealViewerCoordinator]):
    """A MealViewer entity attached to the school device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MealViewerCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        unique_id = coordinator.config_entry.unique_id
        assert unique_id is not None
        school = coordinator.data.school
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=school.name,
            manufacturer="MealViewer",
            model=school.district_lookup,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=school.url,
        )


@callback
def async_add_block_entities(
    entry: MealViewerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[MealViewerCoordinator, str, str], Iterable[Entity]],
) -> None:
    """Add per-meal-block entities now, and for blocks that appear later."""
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = {
            slug: name
            for slug, name in coordinator.data.block_names.items()
            if slug not in known
        }
        known.update(new)
        async_add_entities(
            entity
            for slug, name in new.items()
            for entity in factory(coordinator, slug, name)
        )

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))
