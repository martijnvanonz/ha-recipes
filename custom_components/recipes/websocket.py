"""Websocket commands for the Recipes panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import MAX_SERVINGS
from .scaling import scale_ingredients
from .shopping import async_add_to_list
from .store import RecipeError

_SERVINGS = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_SERVINGS))


def _data(hass: HomeAssistant):
    from . import get_data

    return get_data(hass)


def _handle_errors(func):
    async def wrapper(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
        try:
            await func(hass, connection, msg)
        except RecipeError as err:
            connection.send_error(msg["id"], "invalid", str(err))

    return wrapper


@websocket_api.websocket_command({vol.Required("type"): "recipes/list"})
@websocket_api.async_response
@_handle_errors
async def ws_list(hass, connection, msg) -> None:
    data = _data(hass)
    connection.send_result(
        msg["id"],
        {
            "recipes": [r.as_dict() for r in data.store.sorted()],
            "shopping_list": _user_list(hass, connection),
            "own_shopping_list": data.store.user_lists.get(connection.user.id),
            "default_shopping_list": data.shopping_list,
        },
    )


def _user_list(hass: HomeAssistant, connection: websocket_api.ActiveConnection) -> str:
    data = _data(hass)
    own = data.store.user_lists.get(connection.user.id)
    if own and hass.states.get(own) is not None:
        return own
    return data.shopping_list


@websocket_api.websocket_command(
    {vol.Required("type"): "recipes/set_shopping_list", vol.Required("entity_id"): vol.Any(None, str)}
)
@websocket_api.async_response
@_handle_errors
async def ws_set_list(hass, connection, msg) -> None:
    entity_id = msg["entity_id"]
    if entity_id and (not entity_id.startswith("todo.") or hass.states.get(entity_id) is None):
        raise RecipeError(f"{entity_id} is not a to-do list")
    await _data(hass).store.async_set_user_list(connection.user.id, entity_id)
    connection.send_result(msg["id"], {"shopping_list": _user_list(hass, connection)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recipes/save",
        vol.Optional("recipe_id"): str,
        vol.Optional("title"): str,
        vol.Optional("servings"): _SERVINGS,
        vol.Optional("ingredients"): [str],
        vol.Optional("steps"): [str],
        vol.Optional("photo"): vol.Any(str, None),
    }
)
@websocket_api.async_response
@_handle_errors
async def ws_save(hass, connection, msg) -> None:
    store = _data(hass).store
    data = {k: msg[k] for k in ("title", "servings", "ingredients", "steps") if k in msg}
    if "recipe_id" in msg:
        data["id"] = msg["recipe_id"]
    current = store.recipes.get(msg.get("recipe_id", ""))
    photo = None
    if "photo" in msg:
        if msg["photo"] is None:
            data["remove_photo"] = True
        elif current is None or msg["photo"] != current.photo:
            if not store.photo_exists(msg["photo"]):
                raise RecipeError("Unknown photo; upload it again")
            photo = msg["photo"]
    recipe = await store.async_save_recipe(data, photo)
    connection.send_result(msg["id"], {"recipe": recipe.as_dict()})


@websocket_api.websocket_command({vol.Required("type"): "recipes/delete", vol.Required("recipe_id"): str})
@websocket_api.async_response
@_handle_errors
async def ws_delete(hass, connection, msg) -> None:
    await _data(hass).store.async_delete(msg["recipe_id"])
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {vol.Required("type"): "recipes/scale", vol.Required("recipe_id"): str, vol.Required("servings"): _SERVINGS}
)
@websocket_api.async_response
@_handle_errors
async def ws_scale(hass, connection, msg) -> None:
    recipe = _data(hass).store.find(msg["recipe_id"])
    connection.send_result(
        msg["id"], {"ingredients": scale_ingredients(recipe.ingredients, recipe.servings, msg["servings"])}
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "recipes/add_to_shopping_list", vol.Required("items"): [str]}
)
@websocket_api.async_response
@_handle_errors
async def ws_add(hass, connection, msg) -> None:
    target = _user_list(hass, connection)
    result = await async_add_to_list(hass, target, msg["items"])
    connection.send_result(msg["id"], {**result, "shopping_list": target})


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    for command in (ws_list, ws_save, ws_delete, ws_scale, ws_add, ws_set_list):
        websocket_api.async_register_command(hass, command)
