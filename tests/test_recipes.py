"""Tests for the Recipes integration: store, services, websocket and photo upload."""

from __future__ import annotations

import base64
import io

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from PIL import Image
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.recipes.const import DOMAIN
from custom_components.recipes.scaling import scale_ingredients, scale_line

LIST = "todo.shopping_list"

TACOS = {
    "title": "Taco wraps",
    "servings": 2,
    "ingredients": "- 300 g minced beef\n- 1 red onion\n- 2 cloves garlic\n- ½ tin sweetcorn\n- wraps",
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


def test_scaling() -> None:
    assert scale_line("250 g pasta", 2) == "500 g pasta"
    assert scale_line("½ tin sweetcorn", 2) == "1 tin sweetcorn"
    assert scale_line("1 onion", 1.5) == "1½ onion"
    assert scale_line("0,5 l milk", 3) == "1½ l milk"
    assert scale_line("2-3 cloves garlic", 2) == "4-6 cloves garlic"
    assert scale_line("250g beef", 0.5) == "125g beef"
    assert scale_line("salt and pepper", 2) == "salt and pepper"
    assert scale_ingredients(["1 egg"], 2, 2) == ["1 egg"]
    assert scale_ingredients(["1 egg"], None, 4) == ["1 egg"]


async def test_save_list_update_delete(hass: HomeAssistant, setup) -> None:
    resp = await call(hass, "save", TACOS)
    recipe = resp["recipe"]
    assert recipe["ingredients"][0] == "300 g minced beef"  # list markers removed
    assert recipe["steps"] == ["Chop the onion.", "Fry the beef."]
    assert recipe["photo_url"] is None

    # Update only the servings: the rest stays.
    resp = await call(hass, "save", {"id": recipe["id"], "servings": 3})
    assert resp["recipe"]["servings"] == 3
    assert resp["recipe"]["ingredients"] == recipe["ingredients"]

    await call(hass, "save", {"title": "Pancakes", "servings": 4, "ingredients": ["1 l milk"]})
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
    assert resp["added"] == ["600 g minced beef", "2 red onion", "1 tin sweetcorn"]
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
                        "ingredients": ["250 g pasta", "1 onion"], "steps": ["Boil."], "photo": photo})
    msg = await ws.receive_json()
    assert msg["success"], msg
    rid = msg["result"]["recipe"]["id"]

    await ws.send_json({"id": 2, "type": "recipes/scale", "recipe_id": rid, "servings": 4})
    msg = await ws.receive_json()
    assert msg["result"]["ingredients"] == ["500 g pasta", "2 onion"]

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
