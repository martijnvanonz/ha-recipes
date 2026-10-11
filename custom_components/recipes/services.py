"""Services for Hermes and automations: recipes.save / delete / list / add_to_shopping_list."""

from __future__ import annotations

import base64
import binascii
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MAX_SERVINGS, PHOTO_MAX_BYTES
from .scaling import format_ingredient, scale_ingredients
from .shopping import async_add_to_list, select_items
from .store import RecipeError

_LINES = vol.Any(cv.string, [cv.string])
_INGREDIENT = vol.Any(
    cv.string,
    vol.Schema(
        {
            vol.Optional("amount"): vol.Any(None, cv.string, vol.Coerce(float)),
            vol.Optional("unit"): vol.Any(None, cv.string),
            vol.Required("name"): cv.string,
        }
    ),
)
_INGREDIENTS = vol.Any(cv.string, [_INGREDIENT])
_SERVINGS = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_SERVINGS))

SAVE_SCHEMA = vol.Schema(
    {
        vol.Optional("id"): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("servings"): _SERVINGS,
        vol.Optional("ingredients"): _INGREDIENTS,
        vol.Optional("steps"): _LINES,
        vol.Exclusive("photo_url", "photo"): cv.url,
        vol.Exclusive("photo_base64", "photo"): cv.string,
        vol.Optional("remove_photo"): cv.boolean,
    }
)
DELETE_SCHEMA = vol.Schema({vol.Required("id"): cv.string})
ADD_SCHEMA = vol.Schema(
    {
        vol.Exclusive("id", "recipe"): cv.string,
        vol.Exclusive("title", "recipe"): cv.string,
        vol.Optional("servings"): _SERVINGS,
        vol.Optional("only"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("exclude"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("shopping_list"): cv.entity_domain("todo"),
        vol.Optional("plan", default=True): cv.boolean,
    }
)
PLAN_SCHEMA = vol.Schema(
    {
        vol.Exclusive("id", "recipe"): cv.string,
        vol.Exclusive("title", "recipe"): cv.string,
        vol.Optional("servings"): _SERVINGS,
    }
)


def _data(hass: HomeAssistant):
    from . import get_data

    return get_data(hass)


async def _download(hass: HomeAssistant, url: str) -> bytes:
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=30) as resp:
            resp.raise_for_status()
            content = await resp.content.read(PHOTO_MAX_BYTES + 1)
    except Exception as err:
        raise RecipeError(f"Could not download the photo: {err}") from err
    return content


async def _photo_from_call(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    store = _data(hass).store
    if url := data.get("photo_url"):
        return await store.async_store_photo(await _download(hass, url))
    if b64 := data.get("photo_base64"):
        if "," in b64[:100]:  # data URL
            b64 = b64.split(",", 1)[1]
        try:
            content = base64.b64decode(b64, validate=False)
        except (binascii.Error, ValueError) as err:
            raise RecipeError("photo_base64 is not valid base64") from err
        return await store.async_store_photo(content)
    return None


def async_register_services(hass: HomeAssistant) -> None:
    async def save(call: ServiceCall) -> ServiceResponse:
        try:
            photo = await _photo_from_call(hass, call.data)
            recipe = await _data(hass).store.async_save_recipe(dict(call.data), photo)
        except RecipeError as err:
            raise ServiceValidationError(str(err)) from err
        return {"recipe": recipe.as_dict()}

    async def delete(call: ServiceCall) -> None:
        try:
            await _data(hass).store.async_delete(call.data["id"])
        except RecipeError as err:
            raise ServiceValidationError(str(err)) from err

    async def list_recipes(call: ServiceCall) -> ServiceResponse:
        try:
            store = _data(hass).store
        except RecipeError as err:
            raise HomeAssistantError(str(err)) from err
        return {"recipes": [r.as_dict() for r in store.sorted()]}

    async def add_to_shopping_list(call: ServiceCall) -> ServiceResponse:
        try:
            data = _data(hass)
            recipe = data.store.find(call.data.get("id"), call.data.get("title"))
            target = call.data.get("servings", recipe.servings)
            scaled = scale_ingredients(recipe.ingredients, recipe.servings, target)
            items = [format_ingredient(i) for i in scaled]
            items = select_items(items, call.data.get("only"), call.data.get("exclude"))
            shopping_list = call.data.get("shopping_list", data.shopping_list)
            result = await async_add_to_list(hass, shopping_list, items)
            if call.data["plan"]:
                await data.store.async_plan(recipe.id, target)
        except RecipeError as err:
            raise ServiceValidationError(str(err)) from err
        return {"recipe": recipe.title, "servings": target, "shopping_list": shopping_list, **result}

    async def plan(call: ServiceCall) -> None:
        try:
            store = _data(hass).store
            recipe = store.find(call.data.get("id"), call.data.get("title"))
            await store.async_plan(recipe.id, call.data.get("servings"))
        except RecipeError as err:
            raise ServiceValidationError(str(err)) from err

    async def clear_plan(call: ServiceCall) -> None:
        try:
            await _data(hass).store.async_plan(None)
        except RecipeError as err:
            raise ServiceValidationError(str(err)) from err

    hass.services.async_register(DOMAIN, "plan", plan, PLAN_SCHEMA)
    hass.services.async_register(DOMAIN, "clear_plan", clear_plan, vol.Schema({}))
    hass.services.async_register(DOMAIN, "save", save, SAVE_SCHEMA, SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "delete", delete, DELETE_SCHEMA)
    hass.services.async_register(DOMAIN, "list", list_recipes, vol.Schema({}), SupportsResponse.ONLY)
    hass.services.async_register(
        DOMAIN, "add_to_shopping_list", add_to_shopping_list, ADD_SCHEMA, SupportsResponse.OPTIONAL
    )
