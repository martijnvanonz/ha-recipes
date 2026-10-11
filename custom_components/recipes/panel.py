"""The 'Recipes' sidebar panel."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.core import HomeAssistant, callback

from .const import PANEL_COMPONENT, PANEL_STATIC_URL, PANEL_URL_PATH

_VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text())["version"]


def default_title(hass: HomeAssistant) -> str:
    return "Recepten" if (hass.config.language or "").startswith("nl") else "Recipes"


async def async_register_panel(hass: HomeAssistant, title: str | None = None, *, replace: bool = False) -> None:
    """Add the sidebar item. The title is plain text: HA cannot translate custom panel titles."""
    if "frontend" not in hass.config.components:
        return  # e.g. in tests
    from homeassistant.components import frontend, panel_custom

    if PANEL_URL_PATH in hass.data.get(frontend.DATA_PANELS, {}):
        if not replace:
            return
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    title = title or default_title(hass)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=title,
        sidebar_icon="mdi:chef-hat",
        module_url=f"{PANEL_STATIC_URL}/recipes-panel.js?v={_VERSION}",
        require_admin=False,
    )


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, PANEL_URL_PATH)
