"""Recipe storage (.storage/recipes) and photo files (config/recipes_photos)."""

from __future__ import annotations

import io
import logging
import re
import uuid
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

_LOGGER = logging.getLogger(__name__)
_PHOTO_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|gif)$")


class RecipeError(Exception):
    """Invalid input; the message is shown to the user."""


@dataclass
class Recipe:
    id: str
    title: str
    servings: int
    ingredients: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    photo: str | None = None
    created: str = ""
    updated: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["photo_url"] = f"{PHOTO_URL}/{self.photo}" if self.photo else None
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


class RecipeStore:
    """Keeps all recipes in memory and saves them to .storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.recipes: dict[str, Recipe] = {}
        self.user_lists: dict[str, str] = {}  # HA user id -> to-do entity
        self.photo_dir = Path(hass.config.path(PHOTO_DIR))

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.recipes = {r["id"]: Recipe(**r) for r in data.get("recipes", [])}
        self.user_lists = dict(data.get("user_lists", {}))
        await self.hass.async_add_executor_job(lambda: self.photo_dir.mkdir(exist_ok=True))

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"recipes": [asdict(r) for r in self.recipes.values()], "user_lists": self.user_lists}
        )

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
            recipe.ingredients = lines(data["ingredients"])
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
