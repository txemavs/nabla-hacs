# Home Assistant custom component for Nabla Control (domain: nabla_control).
# Polls ESP mirror devices for display frames and Nabla web UI devices for state.
# See docs/platform/DISPLAY-MIRROR-CONTRACT.md for the HTTP contract.

import asyncio
import logging
import os
import time

import aiohttp
import voluptuous as vol

from homeassistant.components import panel_custom, frontend
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .mqtt_log import MqttLog
from .camera import CameraManager, CAMERA_SCHEMA
from .identity import http_host
from .frame import decode_frame, image_to_png_bytes, infer_profile_from_size
from .websocket import async_register_websocket_handlers

_LOGGER = logging.getLogger(__name__)

DOMAIN = "nabla_control"

CONF_DEVICES = "devices"
CONF_HOST = "host"
CONF_NAME = "name"
CONF_POLL_INTERVAL = "poll_interval"
CONF_KIND = "kind"

DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_KIND = "auto"
KIND_AUTO = "auto"
KIND_MIRROR = "mirror"
KIND_WEB = "web"

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL):
        vol.All(vol.Coerce(float), vol.Range(min=0.2, max=30)),
    vol.Optional(CONF_KIND, default=DEFAULT_KIND): vol.In(
        [KIND_AUTO, KIND_MIRROR, KIND_WEB]
    ),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional("camera_cache"): CAMERA_SCHEMA,
        vol.Optional(CONF_DEVICES, default=[]): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
    })
}, extra=vol.ALLOW_EXTRA)


class DeviceState:
    """Tracks state for one Nabla Control device (mirror display or web UI)."""

    def __init__(
        self,
        host: str,
        name: str,
        poll_interval: float,
        session: aiohttp.ClientSession,
        kind: str = DEFAULT_KIND,
        device_id: str | None = None,
    ):
        self._device_id = device_id or host.replace(".", "_").replace(":", "_")
        self.host = host
        self.name = name
        self.poll_interval = poll_interval
        self.session = session
        self.configured_kind = kind  # auto | mirror | web

        self.capabilities: dict | None = None
        self.capabilities_from_fallback = False
        self.token: str | None = None
        self.last_frame: bytes | None = None
        self.last_png: bytes | None = None
        self.last_update: float = 0
        self.available = False
        self.poll_task: asyncio.Task | None = None
        self._caps_retry_counter = 0

        # Web / Nabla UI fields
        self.kind: str | None = None  # resolved: "web" | "mirror"
        self.web_url: str | None = None
        self.camera_url: str | None = None
        self.has_camera: bool = False
        self.nabla_state: dict | None = None

    @property
    def device_id(self) -> str:
        """Persistent identity; changing the address does not change dashboard IDs."""
        return self._device_id

    @property
    def width(self) -> int:
        return self.capabilities.get("width", 0) if self.capabilities else 0

    @property
    def height(self) -> int:
        return self.capabilities.get("height", 0) if self.capabilities else 0

    @property
    def format(self) -> str:
        return self.capabilities.get("format", "unknown") if self.capabilities else "unknown"

    @property
    def has_input(self) -> bool:
        return self.capabilities.get("input", False) if self.capabilities else False

    @property
    def open_url(self) -> str | None:
        """URL to open the Nabla web UI (alias of web_url)."""
        return self.web_url

    def _apply_web_state(self, state: dict) -> None:
        """Apply /nabla/state JSON as a web device."""
        camera_port = state.get("camera_port")
        has_cam = bool(camera_port)
        self.kind = KIND_WEB
        self.nabla_state = state
        self.web_url = f"http://{http_host(self.host)}/"
        self.has_camera = has_cam
        self.camera_url = (
            f"http://{http_host(self.host)}:{camera_port}/" if has_cam else None
        )
        self.capabilities = {
            "kind": KIND_WEB,
            "width": 0,
            "height": 0,
            "format": "web",
            "input": False,
            "camera": has_cam,
            "camera_port": camera_port,
            "open_url": self.web_url,
        }
        self.capabilities_from_fallback = False
        self.available = True
        self.last_update = time.monotonic()

    async def fetch_nabla_state(self) -> bool:
        """Fetch Nabla web UI /nabla/state JSON. Returns True on success."""
        try:
            url = f"http://{http_host(self.host)}/nabla/state"
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    try:
                        state = await resp.json(content_type=None)
                    except Exception:
                        text = await resp.text()
                        _LOGGER.warning(
                            "Invalid JSON from /nabla/state for %s: %s",
                            self.name, text[:120],
                        )
                        return False
                    if not isinstance(state, dict):
                        _LOGGER.warning(
                            "/nabla/state for %s is not an object", self.name
                        )
                        return False
                    self._apply_web_state(state)
                    _LOGGER.debug(
                        "Nabla web state for %s: camera_port=%s",
                        self.name, state.get("camera_port"),
                    )
                    return True
                _LOGGER.debug(
                    "/nabla/state failed for %s: HTTP %d", self.name, resp.status
                )
        except Exception as e:
            _LOGGER.debug("/nabla/state failed for %s: %s", self.name, e)
        return False

    async def fetch_capabilities(self) -> bool:
        """Fetch mirror device capabilities. Returns True on success."""
        try:
            url = f"http://{http_host(self.host)}/mirror/capabilities"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    self.capabilities = await resp.json()
                    self.capabilities_from_fallback = False
                    self.kind = KIND_MIRROR
                    self.web_url = None
                    self.camera_url = None
                    self.has_camera = False
                    self.nabla_state = None
                    _LOGGER.debug("Capabilities for %s: %s", self.name, self.capabilities)
                    return True
                _LOGGER.warning("Capabilities fetch failed for %s: HTTP %d", self.name, resp.status)
        except Exception as e:
            _LOGGER.warning("Capabilities fetch failed for %s: %s", self.name, e)
        return False

    async def probe_frame_for_fallback(self) -> bool:
        """Probe /mirror/frame to infer profile from size when capabilities unavailable."""
        try:
            url = f"http://{http_host(self.host)}/mirror/frame"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    frame_data = await resp.read()
                    profile = infer_profile_from_size(len(frame_data))
                    if profile:
                        self.capabilities = {
                            "width": profile["width"],
                            "height": profile["height"],
                            "format": profile["format"],
                            "input": False,
                        }
                        self.capabilities_from_fallback = True
                        self.kind = KIND_MIRROR
                        _LOGGER.info(
                            "Inferred %s profile for %s from frame size %d: %dx%d %s (input disabled)",
                            profile["name"], self.name, len(frame_data),
                            profile["width"], profile["height"], profile["format"]
                        )
                        self.last_frame = frame_data
                        return True
                    _LOGGER.warning(
                        "Unknown frame size %d for %s, cannot infer profile",
                        len(frame_data), self.name
                    )
                elif resp.status == 409:
                    _LOGGER.debug("Frame not ready for fallback probe on %s", self.name)
                else:
                    _LOGGER.warning("Frame probe failed for %s: HTTP %d", self.name, resp.status)
        except Exception as e:
            _LOGGER.warning("Frame probe failed for %s: %s", self.name, e)
        return False

    async def fetch_token(self) -> bool:
        """Fetch CSRF token for input. Returns True on success."""
        if not self.has_input:
            return True
        try:
            url = f"http://{http_host(self.host)}/mirror/token"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    self.token = await resp.text()
                    _LOGGER.debug("Token fetched for %s", self.name)
                    return True
                _LOGGER.warning("Token fetch failed for %s: HTTP %d", self.name, resp.status)
        except Exception as e:
            _LOGGER.warning("Token fetch failed for %s: %s", self.name, e)
        return False

    async def fetch_frame(self) -> bool:
        """Fetch current mirror frame. Returns True on success."""
        if not self.capabilities or self.kind == KIND_WEB:
            return False
        try:
            url = f"http://{http_host(self.host)}/mirror/frame"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    self.last_frame = await resp.read()
                    image = decode_frame(
                        self.last_frame, self.width, self.height, self.format
                    )
                    self.last_png = image_to_png_bytes(image)
                    self.last_update = time.monotonic()
                    self.available = True
                    return True
                if resp.status == 409:
                    _LOGGER.debug("Frame not ready for %s", self.name)
                else:
                    _LOGGER.warning("Frame fetch failed for %s: HTTP %d", self.name, resp.status)
        except Exception as e:
            _LOGGER.warning("Frame fetch failed for %s: %s", self.name, e)
        self.available = False
        return False

    async def send_action(self, action: str) -> bool:
        """Send encoder action to device. Returns True on success."""
        if self.kind == KIND_WEB:
            _LOGGER.warning("Cannot send action to web device %s", self.name)
            return False
        if not self.has_input or not self.token:
            _LOGGER.warning("Cannot send action to %s: no input or token", self.name)
            return False

        valid_actions = ("up", "down", "enter", "back")
        if action not in valid_actions:
            _LOGGER.warning("Invalid action '%s' for %s", action, self.name)
            return False

        try:
            url = f"http://{http_host(self.host)}/mirror/action"
            headers = {"X-Nabla-Token": self.token}
            data = {"action": action}
            async with self.session.post(
                url, headers=headers, data=data,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    _LOGGER.debug("Action %s sent to %s", action, self.name)
                    return True
                if resp.status == 401:
                    _LOGGER.warning("Token rejected for %s, refetching", self.name)
                    await self.fetch_token()
                else:
                    _LOGGER.warning("Action failed for %s: HTTP %d", self.name, resp.status)
        except Exception as e:
            _LOGGER.warning("Action failed for %s: %s", self.name, e)
        return False

    async def _discover_kind(self) -> bool:
        """Resolve device kind for auto / first connect. Returns True if ready."""
        prefer = self.configured_kind

        if prefer == KIND_WEB:
            if await self.fetch_nabla_state():
                return True
            self.available = False
            return False

        if prefer == KIND_MIRROR:
            if await self.fetch_capabilities():
                await self.fetch_token()
                return True
            if await self.probe_frame_for_fallback():
                return True
            return False

        # auto: prefer /nabla/state fingerprint, then mirror
        if await self.fetch_nabla_state():
            _LOGGER.info("Detected Nabla web UI on %s", self.name)
            return True
        if await self.fetch_capabilities():
            await self.fetch_token()
            return True
        if await self.probe_frame_for_fallback():
            return True
        return False

    async def poll_loop(self):
        """Background polling loop for frame or web state updates."""
        while True:
            if not self.capabilities or self.kind is None:
                if not await self._discover_kind():
                    await asyncio.sleep(5)
                    continue

            if self.kind == KIND_WEB:
                ok = await self.fetch_nabla_state()
                if not ok:
                    self.available = False
                    if self.configured_kind == KIND_AUTO:
                        self.capabilities = None
                        self.kind = None
                await asyncio.sleep(self.poll_interval)
                continue

            # Mirror path
            if self.capabilities_from_fallback:
                self._caps_retry_counter += 1
                if self._caps_retry_counter >= 10:
                    self._caps_retry_counter = 0
                    if await self.fetch_capabilities():
                        _LOGGER.info("Upgraded %s from fallback to real capabilities", self.name)
                        await self.fetch_token()

            await self.fetch_frame()
            await asyncio.sleep(self.poll_interval)

    def start_polling(self):
        """Start the background polling task."""
        if self.poll_task is None:
            self.poll_task = asyncio.create_task(self.poll_loop())

    async def stop_polling(self):
        """Stop the background polling task."""
        if self.poll_task:
            self.poll_task.cancel()
            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass
            self.poll_task = None


PANEL_TITLE = "Nabla Control"
PANEL_ICON = "nabla:logo"
PANEL_URL_PATH = "nabla-control"
PANEL_FRONTEND_URL = f"/{DOMAIN}_panel"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the sidebar panel for device management."""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")

    await hass.http.async_register_static_paths([
        StaticPathConfig(PANEL_FRONTEND_URL, frontend_path, cache_headers=False)
    ])

    frontend.add_extra_js_url(hass, f"{PANEL_FRONTEND_URL}/nabla-icons.js?v=1")

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="nabla-panel",
        frontend_url_path=PANEL_URL_PATH,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{PANEL_FRONTEND_URL}/nabla-panel.js?v=20260921cameras1",
        embed_iframe=False,
        require_admin=False,
    )

    _LOGGER.debug("Nabla Control panel registered at /%s", PANEL_URL_PATH)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Nabla Control integration (domain nabla_control)."""
    devices: dict[str, DeviceState] = {}
    hass.data[DOMAIN] = {"devices": devices, "entries": {}}
    monitor = MqttLog(hass)
    hass.data[DOMAIN]["mqtt_log"] = monitor
    await monitor.restore()
    cameras = CameraManager(hass)
    hass.data[DOMAIN]["camera_cache"] = cameras
    cameras.register()

    hass.http.register_view(FrameImageView(devices))

    async_register_websocket_handlers(hass)

    await async_register_panel(hass)

    async def handle_send_action(call: ServiceCall):
        """Handle nabla_control.send_action service call."""
        device_id = call.data.get("device_id")
        action = call.data.get("action")

        if device_id not in devices:
            _LOGGER.error("Unknown device: %s", device_id)
            return

        await devices[device_id].send_action(action)

    hass.services.async_register(
        DOMAIN, "send_action", handle_send_action,
        schema=vol.Schema({
            vol.Required("device_id"): cv.string,
            vol.Required("action"): vol.In(["up", "down", "enter", "back"]),
        })
    )

    # Import legacy YAML once, including offline devices. Existing entries win
    # on subsequent boots so obsolete YAML cannot revert a changed address.
    for device_conf in config.get(DOMAIN, {}).get(CONF_DEVICES, []):
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT},
            data=dict(device_conf),
        ))

    camera_conf = config.get(DOMAIN, {}).get("camera_cache")
    if camera_conf:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT},
            data={"entry_type": "camera_cache", **camera_conf}))

    async def stop(_event):
        await cameras.close()
        monitor.stop()
        for device in list(devices.values()):
            await device.stop_polling()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    return True


async def async_setup_entry(hass, entry) -> bool:
    """Load one device without restarting the server or other devices."""
    data = {**entry.data, **entry.options}
    if data.get("entry_type") == "camera_cache":
        await hass.data[DOMAIN]["camera_cache"].configure(data)
        entry.async_on_unload(entry.add_update_listener(_async_update_entry))
        return True
    device = DeviceState(
        data[CONF_HOST], data.get(CONF_NAME, entry.title),
        data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        async_get_clientsession(hass), kind=data.get(CONF_KIND, DEFAULT_KIND),
        device_id=entry.data["device_id"],
    )
    registry = hass.data[DOMAIN]
    registry["devices"][device.device_id] = device
    registry["entries"][entry.entry_id] = device
    device.start_polling()
    try:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.BUTTON])
    except Exception:
        await device.stop_polling()
        registry["devices"].pop(device.device_id, None)
        registry["entries"].pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(_async_update_entry))
    return True


async def _async_update_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry) -> bool:
    """Cancel polling and unload only this device's entities."""
    if entry.data.get("entry_type") == "camera_cache":
        await hass.data[DOMAIN]["camera_cache"].close()
        return True
    if not await hass.config_entries.async_unload_platforms(entry, [Platform.BUTTON]):
        return False
    device = hass.data[DOMAIN]["entries"].pop(entry.entry_id)
    await device.stop_polling()
    hass.data[DOMAIN]["devices"].pop(device.device_id, None)
    return True


class FrameImageView(HomeAssistantView):
    """HTTP view serving device frame images (mirror PNG only)."""

    url = "/api/nabla_control/{device_id}/frame"
    name = "api:nabla_control:frame"
    requires_auth = True

    def __init__(self, devices: dict[str, DeviceState]):
        self.devices = devices

    async def get(self, request, device_id: str):
        """Handle GET request for frame image."""
        from aiohttp import web

        if device_id not in self.devices:
            return web.Response(status=404, text="Device not found")

        device = self.devices[device_id]

        # Web devices use camera_url MJPEG directly in the panel — no HA proxy.
        if device.kind == KIND_WEB:
            return web.Response(
                status=503,
                text="Web device: use camera_url / open_url from nabla_control/devices",
            )

        if not device.available or device.last_png is None:
            return web.Response(status=503, text="Frame not available")

        return web.Response(
            body=device.last_png,
            content_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-Nabla-Width": str(device.width),
                "X-Nabla-Height": str(device.height),
                "X-Nabla-Format": device.format,
                "X-Nabla-Input": "1" if device.has_input else "0",
            }
        )
