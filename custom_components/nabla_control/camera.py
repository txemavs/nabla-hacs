"""Protected, on-demand camera thumbnails for small displays."""
import asyncio
import time

from aiohttp import web
import voluptuous as vol

from homeassistant.components.camera import CameraView, async_get_image
from homeassistant.components.camera.const import DATA_COMPONENT
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv

from .camera_cache import CameraCache, Unavailable

CAMERA_SCHEMA = vol.Schema({
    vol.Required("cameras"): vol.All(cv.ensure_list, [cv.entity_domain("camera")],
        vol.Length(min=1, max=32), lambda items: list(dict.fromkeys(items))),
    vol.Optional("refresh_interval", default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=60)),
    vol.Optional("max_stale", default=8.0): vol.All(vol.Coerce(float), vol.Range(min=1, max=60)),
    vol.Optional("quality", default=70): vol.All(vol.Coerce(int), vol.Range(min=30, max=85)),
})


class CameraManager:
    """Stable route registry; replacing options never leaves a second cache."""
    def __init__(self, hass):
        self.hass = hass
        self.caches = {}
        self.gate = asyncio.Semaphore(2)

    def register(self):
        component = self.hass.data[DATA_COMPONENT]
        self.hass.http.register_view(CachedImageView(component, self.caches))
        self.hass.http.register_view(LegacyImageView(component, self.caches))

    async def configure(self, options):
        options = CAMERA_SCHEMA({k: options[k] for k in
            ("cameras", "refresh_interval", "max_stale", "quality") if k in options})
        await self.close()
        for entity_id in options["cameras"]:
            async def fetch(entity=entity_id):
                image = await async_get_image(self.hass, entity, timeout=8)
                return image.content
            self.caches[entity_id] = CameraCache(fetch, self.hass.async_add_executor_job,
                self.gate, interval=options["refresh_interval"],
                max_stale=options["max_stale"], quality=options["quality"])

    async def close(self):
        old = list(self.caches.values())
        self.caches.clear()
        await asyncio.gather(*(cache.close() for cache in old))

class CachedImageView(CameraView):
    """Reuse HA's camera authentication (Bearer or rotating camera token)."""

    url = "/api/nabla_control/camera/{entity_id}"
    name = "api:nabla_control:camera"

    def __init__(self, component, caches):
        super().__init__(component)
        self.caches = caches

    async def handle(self, request, camera):
        # CameraView authenticates before reaching either cache or source.
        if camera.entity_id not in self.caches:
            raise web.HTTPNotFound
        size = request.query.get("size", "view")
        if size not in ("icon", "view"):
            raise web.HTTPBadRequest(text="size must be icon or view")
        cache = self.caches[camera.entity_id]
        try:
            frame = await cache.get()
        except Unavailable:
            return web.Response(status=503, text="Camera image unavailable",
                                headers={"Retry-After": "2", "Cache-Control": "no-store"})
        age = max(0.0, time.monotonic() - frame.created)
        headers = {
            "Cache-Control": "private, no-cache",
            "ETag": frame.etags[size],
            "X-Nabla-Age": f"{age:.3f}",
            "X-Nabla-Stale": "1" if age >= cache.interval else "0",
            "X-Nabla-Generation": str(frame.generation),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        }
        if request.headers.get("If-None-Match") == frame.etags[size]:
            return web.Response(status=304, headers=headers)
        return web.Response(body=frame.images[size], content_type="image/jpeg",
                            headers=headers)


class LegacyImageView(CachedImageView):
    """Compatibility for deployed firmware; same authentication and cache."""
    url = "/api/nabla_camera/{entity_id}"
    name = "api:nabla_camera:image"
