"""Config flow: pick the shopping list (a to-do entity)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_SHOPPING_LIST, DEFAULT_SHOPPING_LIST, DOMAIN


def _schema(default: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SHOPPING_LIST, default=default): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="todo")
            )
        }
    )


class RecipesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Recipes", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema(DEFAULT_SHOPPING_LIST))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RecipesOptionsFlow()


class RecipesOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_SHOPPING_LIST, self.config_entry.data.get(CONF_SHOPPING_LIST, DEFAULT_SHOPPING_LIST)
        )
        return self.async_show_form(step_id="init", data_schema=_schema(current))
