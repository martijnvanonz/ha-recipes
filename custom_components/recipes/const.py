"""Constants for the Recipes integration."""

from __future__ import annotations

DOMAIN = "recipes"

CONF_SHOPPING_LIST = "shopping_list"
DEFAULT_SHOPPING_LIST = "todo.shopping_list"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

PHOTO_DIR = "recipes_photos"
PHOTO_URL = "/api/recipes/photos"
UPLOAD_URL = "/api/recipes/photo"
PANEL_URL_PATH = "recipes"
PANEL_STATIC_URL = "/recipes_static"
PANEL_COMPONENT = "recipes-panel"

PHOTO_MAX_SIZE = 1600
PHOTO_MAX_BYTES = 20 * 1024 * 1024
MAX_SERVINGS = 50
