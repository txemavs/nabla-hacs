# WebSocket API handlers for Nabla Display panel.
# Provides device listing and dashboard management operations.

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register WebSocket handlers for the Nabla Display panel."""
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
    """Return list of all configured Nabla Display devices with their current state."""
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
            "capabilities_from_fallback": device.capabilities_from_fallback,
        })

    connection.send_result(msg["id"], devices)
