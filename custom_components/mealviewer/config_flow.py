"""Config flow for MealViewer."""

from __future__ import annotations

from datetime import time
from typing import Any, override

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)
import probatio

from .api import (
    MealViewerClient,
    MealViewerConnectionError,
    MealViewerSchoolNotFoundError,
    parse_school_lookup,
)
from .const import (
    CONF_DAYS_AHEAD,
    CONF_END,
    CONF_MEAL_TIMES,
    CONF_ROLLOVER_TIME,
    CONF_SCHOOL,
    CONF_START,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_ROLLOVER_TIME,
    DOMAIN,
    LOGGER,
)
from .coordinator import MealViewerConfigEntry

USER_SCHEMA = probatio.Schema({probatio.Required(CONF_SCHOOL): str})
MEAL_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_START): TimeSelector(),
        probatio.Optional(CONF_END): TimeSelector(),
    }
)
EXAMPLE_URL = "https://schools.mealviewer.com/school/AppletonElementarySchool"


class MealViewerConfigFlow(ConfigFlow, domain=DOMAIN):
    """MealViewer config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: MealViewerConfigEntry,
    ) -> MealViewerOptionsFlow:
        """Options flow."""
        return MealViewerOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a school lookup or URL."""
        errors: dict[str, str] = {}
        if user_input is not None:
            lookup = parse_school_lookup(user_input[CONF_SCHOOL])
            client = MealViewerClient(async_get_clientsession(self.hass), lookup)
            try:
                school = await client.get_school()
            except MealViewerSchoolNotFoundError:
                errors[CONF_SCHOOL] = "school_not_found"
            except MealViewerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(school.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=school.name, data={CONF_SCHOOL: school.lookup}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
            description_placeholders={"example_url": EXAMPLE_URL},
        )


class MealViewerOptionsFlow(OptionsFlowWithReload):
    """MealViewer options: general settings, then serving times per meal."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._options: dict[str, Any] = {}
        self._meals: list[tuple[str, str]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage general options."""
        options = self.config_entry.options
        if user_input is not None:
            self._options = {
                **user_input,
                CONF_DAYS_AHEAD: int(user_input[CONF_DAYS_AHEAD]),
                # Keep times for meals not in the current window.
                CONF_MEAL_TIMES: dict(options.get(CONF_MEAL_TIMES, {})),
            }
            if self.config_entry.state is ConfigEntryState.LOADED:
                menu = self.config_entry.runtime_data.coordinator.data
                self._meals = list(menu.block_names.items())
            return await self.async_step_meal()
        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_DAYS_AHEAD,
                    default=options.get(CONF_DAYS_AHEAD, DEFAULT_DAYS_AHEAD),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=60, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                probatio.Required(
                    CONF_ROLLOVER_TIME,
                    default=options.get(CONF_ROLLOVER_TIME, DEFAULT_ROLLOVER_TIME),
                ): TimeSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_meal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional serving times for one meal; repeats for each meal."""
        errors: dict[str, str] = {}
        if user_input is not None:
            slug = self._meals[0][0]
            start, end = user_input.get(CONF_START), user_input.get(CONF_END)
            if bool(start) != bool(end):
                errors["base"] = "start_and_end"
            elif start and time.fromisoformat(end) <= time.fromisoformat(start):
                errors["base"] = "end_before_start"
            else:
                if start:
                    self._options[CONF_MEAL_TIMES][slug] = {
                        CONF_START: start,
                        CONF_END: end,
                    }
                else:
                    self._options[CONF_MEAL_TIMES].pop(slug, None)
                self._meals.pop(0)
                user_input = None

        if not self._meals:
            return self.async_create_entry(data=self._options)

        slug, name = self._meals[0]
        current = user_input or self._options[CONF_MEAL_TIMES].get(slug, {})
        return self.async_show_form(
            step_id="meal",
            data_schema=self.add_suggested_values_to_schema(MEAL_SCHEMA, current),
            errors=errors,
            description_placeholders={"meal": name},
        )
