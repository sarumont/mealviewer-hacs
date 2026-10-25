"""Tests for MealViewer setup, entities and services."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.mealviewer.const import (
    CONF_END,
    CONF_MEAL_TIMES,
    CONF_SCHOOL,
    CONF_START,
    DOMAIN,
)

from .conftest import MENU_URL

LUNCH_SENSOR = "sensor.appleton_elementary_school_next_lunch"
LUNCH_CALENDAR = "calendar.appleton_elementary_school_lunch"
SCHOOL_DAY = "binary_sensor.appleton_elementary_school_school_day"


def _local(*args: int) -> datetime:
    return datetime(*args, tzinfo=dt_util.get_default_time_zone())


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def morning(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Thursday 2026-10-22, 09:00 local."""
    freezer.move_to(_local(2026, 10, 22, 9))
    return freezer


async def test_setup_entities(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    morning: FrozenDateTimeFactory,
) -> None:
    """Entities reflect today's menu, then roll over at noon."""
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert str(mock_api.mock_calls[0][1]).endswith(
        "/school/AppletonElementarySchool/10-22-2026/11-5-2026/0"
    )

    state = hass.states.get(LUNCH_SENSOR)
    assert state.state == "Homestyle turkey & gravy, Deli slider"
    assert state.attributes["date"] == "2026-10-22"
    assert state.attributes["entrees"] == ["Homestyle turkey & gravy", "Deli slider"]
    assert state.attributes["items"][0]["nutrients"]["calories"]["value"] == 201

    assert hass.states.get(SCHOOL_DAY).state == "on"
    assert hass.states.get("sensor.appleton_elementary_school_next_breakfast")

    calendar = hass.states.get(LUNCH_CALENDAR)
    assert calendar.attributes["message"] == "Homestyle turkey & gravy, Deli slider"
    assert "Entrees\n- Homestyle turkey & gravy" in calendar.attributes["description"]
    registry_entry = er.async_get(hass).async_get(LUNCH_CALENDAR)
    assert registry_entry.options[CALENDAR_DOMAIN] == {"color": "#1bb18c"}

    morning.move_to(_local(2026, 10, 22, 12, 0, 1))
    async_fire_time_changed(hass, _local(2026, 10, 22, 12))
    await hass.async_block_till_done()
    assert hass.states.get(LUNCH_SENSOR).attributes["date"] == "2026-10-23"

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_weekend(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """On Saturday, no school; next lunch is Monday."""
    freezer.move_to(_local(2026, 10, 24, 9))
    await _setup(hass, config_entry)
    assert hass.states.get(SCHOOL_DAY).state == "off"
    state = hass.states.get(LUNCH_SENSOR)
    assert state.attributes["date"] == "2026-10-26"
    assert state.state == "Cheesy baked ziti, Uncrustables"


async def test_setup_retry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """API failure defers setup."""
    aioclient_mock.get(MENU_URL, status=500)
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_calendar_events(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    morning: FrozenDateTimeFactory,
) -> None:
    """Cached range serves calendar events without another request."""
    await _setup(hass, config_entry)
    calls = mock_api.call_count
    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            "entity_id": LUNCH_CALENDAR,
            "start_date_time": "2026-10-22T00:00:00",
            "end_date_time": "2026-10-27T00:00:00",
        },
        blocking=True,
        return_response=True,
    )
    events = result[LUNCH_CALENDAR]["events"]
    assert [e["start"] for e in events] == ["2026-10-22", "2026-10-23", "2026-10-26"]
    assert events[0]["end"] == "2026-10-23"
    assert events[1]["summary"] == "Bean & cheese burrito, Uncrustables"
    assert mock_api.call_count == calls


async def test_get_menu_service(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    morning: FrozenDateTimeFactory,
) -> None:
    """get_menu returns everything, filtered by block and category."""
    await _setup(hass, config_entry)
    result = await hass.services.async_call(
        DOMAIN,
        "get_menu",
        {
            "config_entry_id": config_entry.entry_id,
            "start_date": "2026-10-22",
            "end_date": "2026-10-24",
            "blocks": ["Lunch"],
            "categories": ["entrees"],
        },
        blocking=True,
        return_response=True,
    )
    assert result["school"]["name"] == "Appleton Elementary School"
    assert result["info"]["prices"]
    assert [d["date"] for d in result["days"]] == [
        "2026-10-22",
        "2026-10-23",
        "2026-10-24",
    ]
    assert result["days"][2]["is_school_day"] is False
    thursday = result["days"][0]["blocks"]
    assert [b["name"] for b in thursday] == ["Lunch"]
    items = thursday[0]["lines"][0]["items"]
    assert {i["category"] for i in items} == {"ENTREES"}
    assert items[0]["allergens"][0]["name"] == "Gluten"


async def test_timed_calendar(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    morning: FrozenDateTimeFactory,
) -> None:
    """Serving times make events timed; the calendar is on only while served."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Appleton Elementary School",
        unique_id="9003",
        data={CONF_SCHOOL: "AppletonElementarySchool"},
        options={
            CONF_MEAL_TIMES: {"lunch": {CONF_START: "11:15:00", CONF_END: "12:30:00"}}
        },
    )
    await _setup(hass, entry)

    state = hass.states.get(LUNCH_CALENDAR)
    assert state.state == "off"
    assert state.attributes["start_time"] == "2026-10-22 11:15:00"
    assert state.attributes["end_time"] == "2026-10-22 12:30:00"
    assert state.attributes["all_day"] is False
    # Breakfast has no times, so it stays all-day (and on).
    breakfast = hass.states.get("calendar.appleton_elementary_school_breakfast")
    assert breakfast.attributes["all_day"] is True

    morning.move_to(_local(2026, 10, 22, 11, 30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(LUNCH_CALENDAR).state == "on"

    morning.move_to(_local(2026, 10, 22, 12, 31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(LUNCH_CALENDAR)
    assert state.state == "off"
    assert state.attributes["start_time"] == "2026-10-23 11:15:00"

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            "entity_id": LUNCH_CALENDAR,
            "start_date_time": "2026-10-22T00:00:00",
            "end_date_time": "2026-10-24T00:00:00",
        },
        blocking=True,
        return_response=True,
    )
    events = result[LUNCH_CALENDAR]["events"]
    assert [(e["start"], e["end"]) for e in events] == [
        ("2026-10-22T11:15:00-07:00", "2026-10-22T12:30:00-07:00"),
        ("2026-10-23T11:15:00-07:00", "2026-10-23T12:30:00-07:00"),
    ]
