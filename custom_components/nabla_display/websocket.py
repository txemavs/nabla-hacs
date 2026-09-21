# WebSocket API handlers for Nabla Control panel (domain: nabla_display).
# Provides device listing for the sidebar panel.

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

DOMAIN = "nabla_display"

_LOGGER = logging.getLogger(__name__)


def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register WebSocket handlers for the Nabla Control panel."""
    websocket_api.async_register_command(hass, websocket_get_devices)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "nabla_display/devices",
    }
)
@callback
def websocket_get_devices(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return list of all configured Nabla Control devices with their current state."""
    data = hass.data.get(DOMAIN, {})
    devices_dict = data.get("devices", {})

    devices = []
    for device_id, device in devices_dict.items():
        devices.append({
            "device_id": device_id,
            "name": device.name,
            "host": device.host,
            "available": device.available,
            "width": device.width,
            "height": device.height,
            "format": device.format,
            "has_input": device.has_input,
            "poll_interval": device.poll_interval,
            "capabilities_from_fallback": getattr(device, "capabilities_from_fallback", False),
            "kind": getattr(device, "kind", None) or "mirror",
            "has_camera": bool(getattr(device, "has_camera", False)),
            "camera_url": getattr(device, "camera_url", None),
            "open_url": getattr(device, "web_url", None) or getattr(device, "open_url", None),
            "web_url": getattr(device, "web_url", None),
        })

    connection.send_result(msg["id"], devices)
