"""Tests for the MealViewer config flow."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.mealviewer.const import (
    CONF_DAYS_AHEAD,
    CONF_ROLLOVER_TIME,
    CONF_SCHOOL,
    DOMAIN,
)

from .conftest import SCHOOL_URL, load_json


async def test_user_flow(hass: HomeAssistant, mock_api: AiohttpClientMocker) -> None:
    """A pasted URL creates an entry keyed by school id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert "example_url" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SCHOOL: "https://schools.mealviewer.com/school/AppletonElementarySchool"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Appleton Elementary School"
    assert result["data"] == {CONF_SCHOOL: "AppletonElementarySchool"}
    assert result["result"].unique_id == "9003"
    assert str(mock_api.mock_calls[0][1]).endswith(
        "/physicalLocation/AppletonElementarySchool"
    )


async def test_user_flow_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Not-found and connection errors are shown, then recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    aioclient_mock.get(SCHOOL_URL, status=404)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SCHOOL: "Nope"}
    )
    assert result["errors"] == {CONF_SCHOOL: "school_not_found"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(SCHOOL_URL, status=500)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SCHOOL: "Nope"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(SCHOOL_URL, json=load_json("school.json"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SCHOOL: "AppletonElementarySchool"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The same school can't be added twice."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SCHOOL: "AppletonElementarySchool"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Options are stored with an int day count."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DAYS_AHEAD: 7.0, CONF_ROLLOVER_TIME: "13:30:00"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_DAYS_AHEAD: 7, CONF_ROLLOVER_TIME: "13:30:00"}
    assert config_entry.runtime_data.coordinator.days_ahead == 7
