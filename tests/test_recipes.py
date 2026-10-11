"""Tests for the Recipes integration: store, services, websocket and photo upload."""

from __future__ import annotations

import base64
import io

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from PIL import Image
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.recipes.const import DOMAIN
from custom_components.recipes.scaling import (
    AmountError,
    ingredient_from_text,
    normalize_amount,
    scale_amount,
    scale_ingredients,
)

LIST = "todo.shopping_list"

TACOS = {
    "title": "Taco wraps",
    "servings": 2,
    "ingredients": [
        {"amount": "300", "unit": "g", "name": "minced beef"},
        {"amount": 1, "name": "red onion"},
        {"amount": "2", "unit": "cloves", "name": "garlic"},
        {"amount": "0,5", "unit": "tin", "name": "sweetcorn"},
        {"name": "wraps"},
    ],
    "steps": ["Chop the onion.", "Fry the beef."],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def setup(hass: HomeAssistant) -> MockConfigEntry:
    shopping = MockConfigEntry(domain="shopping_list")
    shopping.add_to_hass(hass)
    assert await hass.config_entries.async_setup(shopping.entry_id)
    assert await async_setup_component(hass, "http", {})
    # shopping_list keeps its file in the shared test config dir: start empty.
    resp = await hass.services.async_call("todo", "get_items", {"entity_id": LIST}, blocking=True, return_response=True)
    if items := [i["uid"] for i in resp[LIST]["items"]]:
        await hass.services.async_call("todo", "remove_item", {"entity_id": LIST, "item": items}, blocking=True)
    entry = MockConfigEntry(domain=DOMAIN, data={"shopping_list": LIST})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def call(hass: HomeAssistant, service: str, data: dict | None = None, response: bool = True):
    return await hass.services.async_call(DOMAIN, service, data or {}, blocking=True, return_response=response)


async def items_on_list(hass: HomeAssistant) -> list[str]:
    resp = await hass.services.async_call(
        "todo", "get_items", {"entity_id": LIST}, blocking=True, return_response=True
    )
    return [i["summary"] for i in resp[LIST]["items"]]


def jpeg_bytes(size=(3000, 2000)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, "JPEG")
    return buf.getvalue()


def test_amounts_and_scaling() -> None:
    assert [normalize_amount(a) for a in ("250", "0,5", "0.5", "1/2", "1 1/2", "1½", "2-3", 2, 0.25, "", None)] == [
        "250", "½", "½", "½", "1½", "1½", "2-3", "2", "¼", "", ""]
    for bad in ("a pinch", "red", "1/0", "2x"):
        with pytest.raises(AmountError):
            normalize_amount(bad)
    assert scale_amount("250", 2) == "500"
    assert scale_amount("½", 2) == "1"
    assert scale_amount("1", 1.5) == "1½"
    assert scale_amount("0,4", 3) == "1,2"
    assert scale_amount("2-3", 2) == "4-6"
    assert scale_amount("", 2) == ""
    egg = [{"amount": "1", "unit": "", "name": "egg"}]
    assert scale_ingredients(egg, 2, 2) == egg
    assert scale_ingredients(egg, None, 4) == egg
    # Text lines: only a leading number is split off, nothing else is guessed.
    assert ingredient_from_text("1 red onion") == {"amount": "1", "unit": "", "name": "red onion"}
    assert ingredient_from_text("300 g minced beef") == {"amount": "300", "unit": "", "name": "g minced beef"}
    assert ingredient_from_text("salt and pepper") == {"amount": "", "unit": "", "name": "salt and pepper"}
    assert ingredient_from_text("7up") == {"amount": "", "unit": "", "name": "7up"}


async def test_save_list_update_delete(hass: HomeAssistant, setup) -> None:
    resp = await call(hass, "save", TACOS)
    recipe = resp["recipe"]
    assert recipe["ingredients"][0] == {"amount": "300", "unit": "g", "name": "minced beef"}
    assert recipe["ingredients"][3] == {"amount": "½", "unit": "tin", "name": "sweetcorn"}  # normalized
    assert recipe["ingredients_text"][1] == "1 red onion"
    assert recipe["steps"] == ["Chop the onion.", "Fry the beef."]
    assert recipe["photo_url"] is None

    # Update only the servings: the rest stays.
    resp = await call(hass, "save", {"id": recipe["id"], "servings": 3})
    assert resp["recipe"]["servings"] == 3
    assert resp["recipe"]["ingredients"] == recipe["ingredients"]

    resp = await call(hass, "save", {"title": "Pancakes", "servings": 4, "ingredients": "- 1 l milk\n- 2 eggs"})
    assert resp["recipe"]["ingredients"][1] == {"amount": "2", "unit": "", "name": "eggs"}  # text lines work too

    with pytest.raises(ServiceValidationError):
        await call(hass, "save", {"title": "Bad", "ingredients": [{"amount": "a pinch", "name": "salt"}]})
    listed = (await call(hass, "list"))["recipes"]
    assert [r["title"] for r in listed] == ["Pancakes", "Taco wraps"]

    await call(hass, "delete", {"id": recipe["id"]}, response=False)
    assert [r["title"] for r in (await call(hass, "list"))["recipes"]] == ["Pancakes"]

    with pytest.raises(ServiceValidationError):
        await call(hass, "save", {"servings": 2})  # new recipe without title


async def test_recipes_survive_reload(hass: HomeAssistant, setup) -> None:
    await call(hass, "save", TACOS)
    await hass.config_entries.async_reload(setup.entry_id)
    await hass.async_block_till_done()
    assert [r["title"] for r in (await call(hass, "list"))["recipes"]] == ["Taco wraps"]


async def test_add_to_shopping_list(hass: HomeAssistant, setup) -> None:
    await call(hass, "save", TACOS)
    await hass.services.async_call("todo", "add_item", {"entity_id": LIST, "item": "Wraps"}, blocking=True)

    resp = await call(hass, "add_to_shopping_list", {"title": "taco", "servings": 4, "exclude": ["garlic"]})
    assert resp["servings"] == 4
    assert resp["added"] == ["600 g minced beef", "2 red onion", "1 tin sweetcorn"]  # amounts scaled
    assert resp["skipped"] == ["wraps"]  # already on the list (case-insensitive)
    assert await items_on_list(hass) == ["Wraps", "600 g minced beef", "2 red onion", "1 tin sweetcorn"]

    resp = await call(hass, "add_to_shopping_list", {"title": "Taco wraps", "only": ["garlic"]})
    assert resp["added"] == ["2 cloves garlic"]

    with pytest.raises(ServiceValidationError):
        await call(hass, "add_to_shopping_list", {"title": "lasagne"})


async def test_photo_base64(hass: HomeAssistant, setup) -> None:
    b64 = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes()).decode()
    recipe = (await call(hass, "save", {**TACOS, "photo_base64": b64}))["recipe"]
    assert recipe["photo_url"].startswith("/api/recipes/photos/")
    path = hass.config.path("recipes_photos", recipe["photo"])
    with Image.open(path) as img:
        assert max(img.size) == 1600  # resized

    recipe2 = (await call(hass, "save", {"id": recipe["id"], "remove_photo": True}))["recipe"]
    assert recipe2["photo"] is None
    import os

    assert not os.path.exists(path)  # old photo removed

    with pytest.raises(ServiceValidationError):
        await call(hass, "save", {**TACOS, "photo_base64": base64.b64encode(b"not an image").decode()})


async def test_photo_url(hass: HomeAssistant, setup, aioclient_mock) -> None:
    aioclient_mock.get("https://example.com/taco.jpg", content=jpeg_bytes((800, 600)))
    recipe = (await call(hass, "save", {**TACOS, "photo_url": "https://example.com/taco.jpg"}))["recipe"]
    assert recipe["photo"].endswith(".jpg")


async def test_websocket_and_upload(hass: HomeAssistant, setup, hass_ws_client, hass_client) -> None:
    client = await hass_client()
    data = {"file": io.BytesIO(jpeg_bytes((500, 400)))}
    resp = await client.post("/api/recipes/photo", data=data)
    assert resp.status == 200
    photo = (await resp.json())["photo"]

    resp = await client.get(f"/api/recipes/photos/{photo}")
    assert resp.status == 200

    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "recipes/save", "title": "Pasta", "servings": 2,
                        "ingredients": [{"amount": "250", "unit": "g", "name": "pasta"}, {"amount": "1", "name": "onion"}],
                        "steps": ["Boil."], "photo": photo})
    msg = await ws.receive_json()
    assert msg["success"], msg
    rid = msg["result"]["recipe"]["id"]

    await ws.send_json({"id": 2, "type": "recipes/scale", "recipe_id": rid, "servings": 4})
    msg = await ws.receive_json()
    assert msg["result"]["items"] == ["500 g pasta", "2 onion"]
    assert msg["result"]["ingredients"][0] == {"amount": "500", "unit": "g", "name": "pasta"}

    await ws.send_json({"id": 3, "type": "recipes/list"})
    msg = await ws.receive_json()
    assert msg["result"]["shopping_list"] == LIST
    assert msg["result"]["recipes"][0]["id"] == rid

    await ws.send_json({"id": 4, "type": "recipes/add_to_shopping_list", "items": ["500 g pasta", "2 onion"]})
    msg = await ws.receive_json()
    assert msg["result"]["added"] == ["500 g pasta", "2 onion"]

    await ws.send_json({"id": 5, "type": "recipes/save", "title": "X", "photo": "0" * 32 + ".jpg"})
    msg = await ws.receive_json()
    assert not msg["success"]

    # Editing without changing the photo keeps it.
    await ws.send_json({"id": 6, "type": "recipes/save", "recipe_id": rid, "title": "Pasta 2", "photo": photo})
    msg = await ws.receive_json()
    assert msg["result"]["recipe"]["photo"] == photo

    await ws.send_json({"id": 7, "type": "recipes/delete", "recipe_id": rid})
    assert (await ws.receive_json())["success"]


async def test_user_shopping_list(hass: HomeAssistant, setup, hass_ws_client) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "recipes/list"})
    res = (await ws.receive_json())["result"]
    assert res["shopping_list"] == LIST and res["own_shopping_list"] is None

    await ws.send_json({"id": 2, "type": "recipes/set_shopping_list", "entity_id": "todo.nope"})
    assert not (await ws.receive_json())["success"]

    await ws.send_json({"id": 3, "type": "recipes/set_shopping_list", "entity_id": LIST})
    assert (await ws.receive_json())["result"]["shopping_list"] == LIST
    await ws.send_json({"id": 4, "type": "recipes/list"})
    assert (await ws.receive_json())["result"]["own_shopping_list"] == LIST

    await ws.send_json({"id": 5, "type": "recipes/add_to_shopping_list", "items": ["1 egg"]})
    assert (await ws.receive_json())["result"]["shopping_list"] == LIST

    await ws.send_json({"id": 6, "type": "recipes/set_shopping_list", "entity_id": None})
    await ws.receive_json()
    await ws.send_json({"id": 7, "type": "recipes/list"})
    assert (await ws.receive_json())["result"]["own_shopping_list"] is None


async def test_service_shopping_list_option(hass: HomeAssistant, setup) -> None:
    await call(hass, "save", TACOS)
    resp = await call(hass, "add_to_shopping_list", {"title": "taco", "shopping_list": LIST, "only": ["wraps"]})
    assert resp["shopping_list"] == LIST and resp["added"] == ["wraps"]
    with pytest.raises(ServiceValidationError):
        await call(hass, "add_to_shopping_list", {"title": "taco", "shopping_list": "todo.missing"})


async def test_migrates_text_ingredients(hass: HomeAssistant, hass_storage) -> None:
    hass_storage["recipes"] = {
        "version": 1,
        "key": "recipes",
        "data": {"recipes": [{"id": "a" * 32, "title": "Old", "servings": 2, "ingredients": ["2 eggs", "salt"],
                              "steps": [], "photo": None, "created": "", "updated": ""}]},
    }
    shopping = MockConfigEntry(domain="shopping_list")
    shopping.add_to_hass(hass)
    assert await hass.config_entries.async_setup(shopping.entry_id)
    assert await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(domain=DOMAIN, data={"shopping_list": LIST})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    recipe = (await call(hass, "list"))["recipes"][0]
    assert recipe["ingredients"] == [{"amount": "2", "unit": "", "name": "eggs"}, {"amount": "", "unit": "", "name": "salt"}]


async def test_planned_recipe(hass: HomeAssistant, setup, hass_ws_client) -> None:
    sensor = "sensor.recipes_planned_recipe"
    assert hass.states.get(sensor).state == "unknown"

    recipe = (await call(hass, "save", TACOS))["recipe"]
    await call(hass, "add_to_shopping_list", {"title": "taco", "servings": 4})
    await hass.async_block_till_done()
    state = hass.states.get(sensor)
    assert state.state == "Taco wraps"
    assert state.attributes["servings"] == 4
    assert state.attributes["ingredients"][0] == "600 g minced beef"  # scaled
    assert state.attributes["steps"] == ["Chop the onion.", "Fry the beef."]

    # Adding without planning keeps the current plan.
    await call(hass, "save", {"title": "Pancakes", "ingredients": [{"amount": 2, "name": "eggs"}]})
    await call(hass, "add_to_shopping_list", {"title": "pancakes", "plan": False})
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == "Taco wraps"

    await call(hass, "plan", {"title": "pancakes", "servings": 6}, response=False)
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == "Pancakes"

    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "recipes/add_to_shopping_list", "items": ["wraps"],
                        "recipe_id": recipe["id"], "servings": 2})
    assert (await ws.receive_json())["success"]
    await ws.send_json({"id": 2, "type": "recipes/list"})
    assert (await ws.receive_json())["result"]["planned"]["title"] == "Taco wraps"

    await call(hass, "clear_plan", response=False)
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == "unknown"

    # Deleting the planned recipe clears the plan.
    await call(hass, "plan", {"id": recipe["id"]}, response=False)
    await call(hass, "delete", {"id": recipe["id"]}, response=False)
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == "unknown"


async def test_panel_title(hass: HomeAssistant, setup, hass_ws_client, hass_admin_user) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "recipes/list"})
    res = (await ws.receive_json())["result"]
    assert res["panel_title"] is None and res["default_panel_title"] == "Recipes"

    await ws.send_json({"id": 2, "type": "recipes/set_panel_title", "title": "  Koken "})
    assert (await ws.receive_json())["result"]["panel_title"] == "Koken"
    await hass.config_entries.async_reload(setup.entry_id)
    ws2 = await hass_ws_client(hass)
    await ws2.send_json({"id": 1, "type": "recipes/list"})
    assert (await ws2.receive_json())["result"]["panel_title"] == "Koken"  # stored

    await ws2.send_json({"id": 2, "type": "recipes/set_panel_title", "title": "x" * 41})
    assert not (await ws2.receive_json())["success"]

    await ws2.send_json({"id": 3, "type": "recipes/set_panel_title", "title": ""})
    assert (await ws2.receive_json())["result"]["panel_title"] == "Recipes"  # back to default

    # Non-admins may not change it.
    hass_admin_user.groups = []
    await ws2.send_json({"id": 4, "type": "recipes/set_panel_title", "title": "Nope"})
    assert (await ws2.receive_json())["error"]["code"] == "unauthorized"


async def test_cooked_counter(hass: HomeAssistant, setup, hass_ws_client) -> None:
    events = []
    hass.bus.async_listen("recipes_cooked", lambda e: events.append(e.data))
    recipe = (await call(hass, "save", TACOS))["recipe"]
    assert recipe["cooked_count"] == 0 and recipe["last_cooked"] is None

    # Clearing without cooked does not count; with cooked it counts once.
    await call(hass, "plan", {"id": recipe["id"]}, response=False)
    await call(hass, "clear_plan", response=False)
    await call(hass, "plan", {"id": recipe["id"]}, response=False)
    await call(hass, "clear_plan", {"cooked": True}, response=False)
    await call(hass, "clear_plan", {"cooked": True}, response=False)  # nothing planned: no double count
    await hass.async_block_till_done()
    listed = (await call(hass, "list"))["recipes"][0]
    assert listed["cooked_count"] == 1 and listed["last_cooked"]
    assert len(events) == 1 and events[0]["cooked_count"] == 1

    # mark_cooked with an older date keeps the newest last_cooked.
    newest = listed["last_cooked"]
    resp = await call(hass, "mark_cooked", {"title": "taco", "date": "2020-01-05"})
    assert resp["cooked_count"] == 2 and resp["last_cooked"] == newest

    # Manual adjust.
    resp = (await call(hass, "save", {"id": recipe["id"], "cooked_count": 7, "last_cooked": "2026-01-02"}))["recipe"]
    assert resp["cooked_count"] == 7 and resp["last_cooked"] == "2026-01-02"

    # Websocket "Done cooking".
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "recipes/plan", "recipe_id": recipe["id"]})
    await ws.receive_json()
    await ws.send_json({"id": 2, "type": "recipes/plan", "recipe_id": None, "cooked": True})
    res = (await ws.receive_json())["result"]
    assert res["planned"] is None and res["cooked"]["cooked_count"] == 8
    await ws.send_json({"id": 3, "type": "recipes/save", "recipe_id": recipe["id"], "cooked_count": 3, "last_cooked": None})
    res = (await ws.receive_json())["result"]["recipe"]
    assert res["cooked_count"] == 3 and res["last_cooked"] is None

    with pytest.raises(vol.Invalid):  # rejected by the service schema
        await call(hass, "save", {"id": recipe["id"], "last_cooked": "not a date"})
