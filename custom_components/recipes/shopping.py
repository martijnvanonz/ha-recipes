"""Put ingredients on a Home Assistant to-do list without duplicates."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.core import HomeAssistant

from .store import RecipeError


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def select_items(ingredients: list[str], only: list[str] | None, exclude: list[str] | None) -> list[str]:
    """Filter ingredient lines: keep lines matching any `only` word, drop lines matching any `exclude` word."""
    items = list(ingredients)
    if only:
        wanted = [_norm(w) for w in only if w.strip()]
        items = [i for i in items if any(w in _norm(i) for w in wanted)]
    if exclude:
        unwanted = [_norm(w) for w in exclude if w.strip()]
        items = [i for i in items if not any(w in _norm(i) for w in unwanted)]
    return items


async def async_add_to_list(hass: HomeAssistant, entity_id: str, items: list[str]) -> dict[str, list[str]]:
    """Add items that are not already open on the list. Returns what was added and skipped."""
    if hass.states.get(entity_id) is None:
        raise RecipeError(f"Shopping list {entity_id} not found")
    response: dict[str, Any] = await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": entity_id, "status": ["needs_action"]},
        blocking=True,
        return_response=True,
    )
    existing = {_norm(i["summary"]) for i in response.get(entity_id, {}).get("items", [])}
    added: list[str] = []
    skipped: list[str] = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        key = _norm(item)
        if key in existing:
            skipped.append(item)
            continue
        await hass.services.async_call("todo", "add_item", {"entity_id": entity_id, "item": item}, blocking=True)
        existing.add(key)
        added.append(item)
    return {"added": added, "skipped": skipped}
