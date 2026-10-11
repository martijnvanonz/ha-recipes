"""sensor.recipes_planned_recipe: the recipe we are going to cook, with its steps."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RecipesConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: RecipesConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([PlannedRecipeSensor(entry)])


class PlannedRecipeSensor(SensorEntity):
    """State: title of the planned recipe. Attributes: servings, ingredients, steps, photo."""

    _attr_has_entity_name = True
    _attr_translation_key = "planned_recipe"
    _attr_icon = "mdi:chef-hat"
    _attr_should_poll = False

    def __init__(self, entry: RecipesConfigEntry) -> None:
        self._store = entry.runtime_data.store
        self._attr_unique_id = f"{entry.entry_id}_planned_recipe"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Recipes",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._store.async_add_listener(self._update))

    @callback
    def _update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        info = self._store.planned_info()
        return info["title"] if info else None

    @property
    def entity_picture(self) -> str | None:
        info = self._store.planned_info()
        return info["photo_url"] if info else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._store.planned_info()
        if not info:
            return {}
        return {
            "recipe_id": info["id"],
            "servings": info["servings"],
            "ingredients": info["ingredients_text"],
            "steps": info["steps"],
            "planned_since": info["planned_since"],
        }
