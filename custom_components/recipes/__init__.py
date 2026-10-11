"""Recipes: keep recipes in Home Assistant and put their ingredients on the shopping list."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_SHOPPING_LIST,
    DEFAULT_SHOPPING_LIST,
    DOMAIN,
    PANEL_STATIC_URL,
    PHOTO_URL,
)
from .http import PhotoUploadView
from .panel import async_register_panel, async_remove_panel
from .services import async_register_services
from .store import RecipeError, RecipeStore
from .websocket import async_register_websocket

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type RecipesConfigEntry = ConfigEntry[RecipesData]


@dataclass
class RecipesData:
    store: RecipeStore
    shopping_list: str


def get_data(hass: HomeAssistant) -> RecipesData:
    """Return the loaded entry data, or raise a user-facing error."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        return entry.runtime_data
    raise RecipeError("The Recipes integration is not loaded")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_services(hass)
    async_register_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RecipesConfigEntry) -> bool:
    store = RecipeStore(hass)
    await store.async_load()
    entry.runtime_data = RecipesData(
        store=store,
        shopping_list=entry.options.get(CONF_SHOPPING_LIST, entry.data.get(CONF_SHOPPING_LIST, DEFAULT_SHOPPING_LIST)),
    )
    # Static paths cannot be removed again, so register them once per HA run.
    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = True
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(PHOTO_URL, str(store.photo_dir), True),
                StaticPathConfig(PANEL_STATIC_URL, str(Path(__file__).parent / "frontend"), False),
            ]
        )
        hass.http.register_view(PhotoUploadView())
    await async_register_panel(hass)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RecipesConfigEntry) -> bool:
    async_remove_panel(hass)
    return True


async def _async_reload(hass: HomeAssistant, entry: RecipesConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
