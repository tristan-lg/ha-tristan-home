"""Config flow pour l'intégration Fuji (litière)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CACA_THRESHOLD,
    CONF_DEBOUNCE_OFF,
    CONF_PIPI_THRESHOLD,
    CONF_PRESENCE_SENSOR,
    DEFAULT_CACA_THRESHOLD,
    DEFAULT_DEBOUNCE_OFF,
    DEFAULT_NAME,
    DEFAULT_PIPI_THRESHOLD,
    DOMAIN,
)

CONF_NAME = "name"


class FujiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gère la configuration initiale de l'intégration Fuji."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PRESENCE_SENSOR])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_PRESENCE_SENSOR: user_input[CONF_PRESENCE_SENSOR]},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_PRESENCE_SENSOR): selector.selector(
                    {"entity": {"domain": "binary_sensor"}}
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return FujiOptionsFlow(config_entry)


class FujiOptionsFlow(OptionsFlow):
    """Gère les options modifiables de l'intégration Fuji."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        options = self._config_entry.options

        if user_input is not None:
            if (
                user_input[CONF_CACA_THRESHOLD]
                <= user_input[CONF_PIPI_THRESHOLD]
            ):
                errors["base"] = "caca_must_be_greater_than_pipi"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PIPI_THRESHOLD,
                    default=options.get(CONF_PIPI_THRESHOLD, DEFAULT_PIPI_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_CACA_THRESHOLD,
                    default=options.get(CONF_CACA_THRESHOLD, DEFAULT_CACA_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_DEBOUNCE_OFF,
                    default=options.get(CONF_DEBOUNCE_OFF, DEFAULT_DEBOUNCE_OFF),
                ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
