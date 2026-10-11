"""Recipe storage (.storage/recipes) and photo files (config/recipes_photos)."""

from __future__ import annotations

import io
import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    MAX_SERVINGS,
    PHOTO_DIR,
    PHOTO_MAX_BYTES,
    PHOTO_MAX_SIZE,
    PHOTO_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .scaling import (
    AmountError,
    format_ingredient,
    ingredient_from_text,
    normalize_amount,
    scale_ingredients,
)

_LOGGER = logging.getLogger(__name__)
_PHOTO_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|gif)$")


class RecipeError(Exception):
    """Invalid input; the message is shown to the user."""


@dataclass
class Recipe:
    id: str
    title: str
    servings: int
    ingredients: list[dict[str, str]] = field(default_factory=list)  # {amount, unit, name}
    steps: list[str] = field(default_factory=list)
    photo: str | None = None
    created: str = ""
    updated: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["photo_url"] = f"{PHOTO_URL}/{self.photo}" if self.photo else None
        data["ingredients_text"] = [format_ingredient(i) for i in self.ingredients]
        return data


def lines(value: Any) -> list[str]:
    """Accept a list or a multi-line string; drop empty lines and list markers."""
    if value is None:
        return []
    items = value.splitlines() if isinstance(value, str) else [str(v) for v in value]
    out = []
    for item in items:
        item = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", item).strip()
        if item:
            out.append(item)
    return out


def ingredients(value: Any) -> list[dict[str, str]]:
    """Accept ingredient objects {amount, unit, name}, text lines, or a multi-line string.

    Objects are stored as given (the amount must be a number). Text lines only get
    a leading number split off; the unit is never guessed.
    """
    if value is None:
        return []
    items = value.splitlines() if isinstance(value, str) else list(value)
    out: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            unit = str(item.get("unit") or "").strip()
            raw_amount = item.get("amount")
            if not name and not unit and raw_amount in (None, ""):
                continue
            if not name:
                raise RecipeError("Every ingredient needs a name")
            try:
                amount = normalize_amount(raw_amount)
            except AmountError as err:
                raise RecipeError(
                    f"'{raw_amount}' is not an amount for {name}; use a number like 2, 0,5, 1/2 or ½"
                ) from err
            out.append({"amount": amount, "unit": unit, "name": name})
        else:
            for line in lines([str(item)]):
                out.append(ingredient_from_text(line))
    return out


class RecipeStore:
    """Keeps all recipes in memory and saves them to .storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.recipes: dict[str, Recipe] = {}
        self.user_lists: dict[str, str] = {}  # HA user id -> to-do entity
        self.planned: dict[str, Any] | None = None  # {"recipe_id", "servings", "since"}
        self.panel_title: str | None = None  # sidebar name; None = default for the server language
        self.photo_dir = Path(hass.config.path(PHOTO_DIR))
        self._listeners: list[Callable[[], None]] = []

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` after every change; returns a function to stop listening."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _changed(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.recipes = {}
        for raw in data.get("recipes", []):
            raw = dict(raw)
            # Version 0.2 stored ingredients as plain text lines.
            raw["ingredients"] = [
                ingredient_from_text(i) if isinstance(i, str) else i for i in raw.get("ingredients", [])
            ]
            self.recipes[raw["id"]] = Recipe(**raw)
        self.user_lists = dict(data.get("user_lists", {}))
        self.planned = data.get("planned")
        self.panel_title = data.get("panel_title")
        if self.planned and self.planned.get("recipe_id") not in self.recipes:
            self.planned = None
        await self.hass.async_add_executor_job(lambda: self.photo_dir.mkdir(exist_ok=True))

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "recipes": [asdict(r) for r in self.recipes.values()],
                "user_lists": self.user_lists,
                "planned": self.planned,
                "panel_title": self.panel_title,
            }
        )
        self._changed()

    def planned_info(self) -> dict[str, Any] | None:
        """The planned recipe with its scaled ingredients, or None."""
        if not self.planned or self.planned["recipe_id"] not in self.recipes:
            return None
        recipe = self.recipes[self.planned["recipe_id"]]
        servings = self.planned.get("servings") or recipe.servings
        scaled = scale_ingredients(recipe.ingredients, recipe.servings, servings)
        return {
            **recipe.as_dict(),
            "servings": servings,
            "recipe_servings": recipe.servings,
            "ingredients": scaled,
            "ingredients_text": [format_ingredient(i) for i in scaled],
            "planned_since": self.planned.get("since"),
        }

    async def async_plan(self, recipe_id: str | None, servings: int | None = None) -> None:
        """Mark a recipe as the one we are going to cook (None: clear)."""
        if recipe_id is None:
            self.planned = None
        else:
            recipe = self.find(recipe_id)
            if servings is not None and not 1 <= int(servings) <= MAX_SERVINGS:
                raise RecipeError(f"Servings must be 1 to {MAX_SERVINGS}")
            self.planned = {
                "recipe_id": recipe.id,
                "servings": int(servings) if servings else recipe.servings,
                "since": dt_util.utcnow().isoformat(),
            }
        await self._async_save()

    async def async_set_panel_title(self, title: str | None) -> None:
        title = (title or "").strip() or None
        if title and len(title) > 40:
            raise RecipeError("The name is too long (max 40 characters)")
        self.panel_title = title
        await self._async_save()

    async def async_set_user_list(self, user_id: str, entity_id: str | None) -> None:
        """Set (or with None: clear) the shopping list of one HA user."""
        if entity_id:
            self.user_lists[user_id] = entity_id
        else:
            self.user_lists.pop(user_id, None)
        await self._async_save()

    def sorted(self) -> list[Recipe]:
        return sorted(self.recipes.values(), key=lambda r: r.title.lower())

    def find(self, recipe_id: str | None = None, title: str | None = None) -> Recipe:
        """Find by id, else by title (exact, then a unique partial match)."""
        if recipe_id:
            if recipe_id in self.recipes:
                return self.recipes[recipe_id]
            raise RecipeError(f"No recipe with id {recipe_id}")
        if not title:
            raise RecipeError("Give a recipe id or title")
        wanted = title.strip().lower()
        exact = [r for r in self.recipes.values() if r.title.lower() == wanted]
        if exact:
            return exact[0]
        partial = [r for r in self.recipes.values() if wanted in r.title.lower()]
        if len(partial) == 1:
            return partial[0]
        if partial:
            raise RecipeError(f"'{title}' matches more recipes: " + ", ".join(r.title for r in partial))
        raise RecipeError(f"No recipe called '{title}'")

    async def async_save_recipe(self, data: dict[str, Any], photo: str | None = None) -> Recipe:
        """Create (no id) or update (id) a recipe. Only given fields change on update."""
        now = dt_util.utcnow().isoformat()
        recipe_id = data.get("id")
        if recipe_id:
            recipe = self.find(recipe_id)
        else:
            if not str(data.get("title") or "").strip():
                raise RecipeError("A new recipe needs a title")
            recipe = Recipe(id=uuid.uuid4().hex, title="", servings=2, created=now)
        if "title" in data:
            title = str(data["title"]).strip()
            if not title:
                raise RecipeError("The title cannot be empty")
            recipe.title = title
        if "servings" in data and data["servings"] is not None:
            servings = int(data["servings"])
            if not 1 <= servings <= MAX_SERVINGS:
                raise RecipeError(f"Servings must be 1 to {MAX_SERVINGS}")
            recipe.servings = servings
        if "ingredients" in data:
            recipe.ingredients = ingredients(data["ingredients"])
        if "steps" in data:
            recipe.steps = lines(data["steps"])
        old_photo = recipe.photo
        if photo is not None or data.get("remove_photo"):
            recipe.photo = photo
        recipe.updated = now
        self.recipes[recipe.id] = recipe
        await self._async_save()
        if old_photo and old_photo != recipe.photo:
            await self._async_delete_photo(old_photo)
        return recipe

    async def async_delete(self, recipe_id: str) -> None:
        recipe = self.find(recipe_id)
        del self.recipes[recipe.id]
        if self.planned and self.planned.get("recipe_id") == recipe.id:
            self.planned = None
        await self._async_save()
        if recipe.photo:
            await self._async_delete_photo(recipe.photo)

    def photo_exists(self, name: str) -> bool:
        return bool(_PHOTO_NAME.match(name)) and (self.photo_dir / name).is_file()

    async def async_store_photo(self, content: bytes) -> str:
        """Save an uploaded image (resized JPEG when Pillow is present); return its file name."""
        if not content:
            raise RecipeError("The photo is empty")
        if len(content) > PHOTO_MAX_BYTES:
            raise RecipeError("The photo is too big (max 20 MB)")
        return await self.hass.async_add_executor_job(self._store_photo, content)

    def _store_photo(self, content: bytes) -> str:
        name = uuid.uuid4().hex
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
        except ImportError:  # pragma: no cover - Pillow ships with Home Assistant
            kind = _sniff(content)
            (self.photo_dir / f"{name}.{kind}").write_bytes(content)
            return f"{name}.{kind}"
        try:
            image = Image.open(io.BytesIO(content))
            image = ImageOps.exif_transpose(image)
        except (UnidentifiedImageError, OSError) as err:
            raise RecipeError("This file is not a photo") from err
        image.thumbnail((PHOTO_MAX_SIZE, PHOTO_MAX_SIZE))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(self.photo_dir / f"{name}.jpg", "JPEG", quality=85, optimize=True)
        return f"{name}.jpg"

    async def _async_delete_photo(self, name: str) -> None:
        if not _PHOTO_NAME.match(name):
            return
        path = self.photo_dir / name
        await self.hass.async_add_executor_job(lambda: path.unlink(missing_ok=True))


def _sniff(content: bytes) -> str:  # pragma: no cover
    if content[:3] == b"\xff\xd8\xff":
        return "jpg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content[:3] == b"GIF":
        return "gif"
    raise RecipeError("This file is not a photo")
