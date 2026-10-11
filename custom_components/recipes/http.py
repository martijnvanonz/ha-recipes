"""Photo upload endpoint for the panel (POST multipart, field 'file')."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import PHOTO_MAX_BYTES, UPLOAD_URL
from .store import RecipeError


class PhotoUploadView(HomeAssistantView):
    url = UPLOAD_URL
    name = "api:recipes:photo"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        from . import get_data

        hass = request.app["hass"]
        request._client_max_size = PHOTO_MAX_BYTES + 1024 * 1024
        try:
            reader = await request.multipart()
            part = await reader.next()
            while part is not None and part.name != "file":
                part = await reader.next()
            if part is None:
                raise RecipeError("No file in the upload")
            content = await part.read(decode=False)
            name = await get_data(hass).store.async_store_photo(bytes(content))
        except RecipeError as err:
            return self.json_message(str(err), HTTPStatus.BAD_REQUEST)
        return self.json({"photo": name})
