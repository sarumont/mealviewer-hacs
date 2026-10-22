"""Data update coordinator for MealViewer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MealViewerClient, MealViewerError
from .const import (
    CONF_DAYS_AHEAD,
    CONF_END,
    CONF_MEAL_TIMES,
    CONF_ROLLOVER_TIME,
    CONF_START,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_ROLLOVER_TIME,
    DOMAIN,
    LOGGER,
    UPDATE_INTERVAL,
)
from .models import Menu


@dataclass
class MealViewerData:
    """Runtime data for a MealViewer config entry."""

    client: MealViewerClient
    coordinator: MealViewerCoordinator


type MealViewerConfigEntry = ConfigEntry[MealViewerData]


class MealViewerCoordinator(DataUpdateCoordinator[Menu]):
    """Fetches a rolling window of menus for one school."""

    config_entry: MealViewerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MealViewerConfigEntry,
        client: MealViewerClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"MealViewer {client.school}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        options = config_entry.options
        self.days_ahead: int = int(options.get(CONF_DAYS_AHEAD, DEFAULT_DAYS_AHEAD))
        self.rollover: time = time.fromisoformat(
            options.get(CONF_ROLLOVER_TIME, DEFAULT_ROLLOVER_TIME)
        )
        # slug -> (start, end) serving times; meals without times stay all-day.
        self.meal_times: dict[str, tuple[time, time]] = {
            slug: (time.fromisoformat(t[CONF_START]), time.fromisoformat(t[CONF_END]))
            for slug, t in options.get(CONF_MEAL_TIMES, {}).items()
        }
        self.window: tuple[date, date] | None = None

    @callback
    def async_setup_timers(self) -> None:
        """Refresh at midnight and recompute states at rollover."""
        self.config_entry.async_on_unload(
            async_track_time_change(
                self.hass, self._async_midnight, hour=0, minute=0, second=0
            )
        )
        self.config_entry.async_on_unload(
            async_track_time_change(
                self.hass,
                self._async_rollover,
                hour=self.rollover.hour,
                minute=self.rollover.minute,
                second=self.rollover.second,
            )
        )

    async def _async_midnight(self, _now: datetime) -> None:
        await self.async_request_refresh()

    @callback
    def _async_rollover(self, _now: datetime) -> None:
        self.async_update_listeners()

    def target_date(self) -> date:
        """Date 'next' sensors look from: today, or tomorrow past rollover."""
        now = dt_util.now()
        if now.time() >= self.rollover:
            return now.date() + timedelta(days=1)
        return now.date()

    @override
    async def _async_update_data(self) -> Menu:
        start = dt_util.now().date()
        end = start + timedelta(days=self.days_ahead)
        try:
            menu = await self.client.get_menu(start, end)
        except MealViewerError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.window = (start, end)
        return menu

    async def async_get_range(self, start: date, end: date) -> Menu:
        """Menus for a range, from cache when it falls inside the window."""
        if self.window and self.window[0] <= start and end <= self.window[1]:
            days = {d: v for d, v in self.data.days.items() if start <= d <= end}
            return Menu(self.data.school, self.data.info, days)
        return await self.client.get_menu(start, end)
