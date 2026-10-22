"""Config flow for MealViewer."""

from __future__ import annotations

from typing import Any, override

from homeassistant.config_entries import (
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
    CONF_ROLLOVER_TIME,
    CONF_SCHOOL,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_ROLLOVER_TIME,
    DOMAIN,
    LOGGER,
)
from .coordinator import MealViewerConfigEntry

USER_SCHEMA = probatio.Schema({probatio.Required(CONF_SCHOOL): str})


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
        )


class MealViewerOptionsFlow(OptionsFlowWithReload):
    """MealViewer options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(
                data={**user_input, CONF_DAYS_AHEAD: int(user_input[CONF_DAYS_AHEAD])}
            )
        options = self.config_entry.options
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
