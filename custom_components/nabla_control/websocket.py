# WebSocket API handlers for Nabla Control panel (domain: nabla_control).
# Provides device listing for the sidebar panel.

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

DOMAIN = "nabla_control"

_LOGGER = logging.getLogger(__name__)


def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register WebSocket handlers for the Nabla Control panel."""
    websocket_api.async_register_command(hass, websocket_get_devices)
    websocket_api.async_register_command(hass, websocket_mqtt_log)
    websocket_api.async_register_command(hass, websocket_cameras)
    websocket_api.async_register_command(hass, websocket_discovery)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "nabla_control/devices",
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


@websocket_api.websocket_command({vol.Required('type'): 'nabla_control/mqtt_log',
    vol.Optional('operation', default='get'): vol.In(['get', 'configure', 'clear']),
    vol.Optional('enabled', default=False): bool,
    vol.Optional('topics', default=[]): [str],
    vol.Optional('limit', default=200): vol.All(int, vol.Range(min=50, max=1000))})
@websocket_api.async_response
async def websocket_mqtt_log(hass, connection, msg):
    """Only administrators may inspect arbitrary MQTT traffic or change filters."""
    connection.require_admin()
    monitor = hass.data[DOMAIN]['mqtt_log']
    try:
        if msg['operation'] == 'configure':
            await monitor.configure(msg)
        elif msg['operation'] == 'clear':
            monitor.buffer.clear()
        connection.send_result(msg['id'], monitor.snapshot())
    except (ValueError, RuntimeError) as exc:
        connection.send_error(msg['id'], 'mqtt_log_error', str(exc))


@websocket_api.websocket_command({vol.Required("type"): "nabla_control/cameras"})
@callback
def websocket_cameras(hass, connection, msg):
    result = []
    for entity_id, cache in hass.data[DOMAIN]["camera_cache"].caches.items():
        if not connection.user.permissions.check_entity(entity_id, "read"):
            continue
        state = hass.states.get(entity_id)
        result.append({"entity_id": entity_id,
            "name": state.name if state else entity_id,
            "interval": cache.interval, "generations": cache.generations,
            "failures": cache.failures})
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "nabla_control/discovery",
    vol.Optional("operation", default="scan"): vol.In(["scan", "adopt"]),
    vol.Optional("source_entry_id"): str})
@websocket_api.async_response
async def websocket_discovery(hass, connection, msg):
    """Administrators explicitly add or bind entries; scans are read-only."""
    connection.require_admin()
    manager = hass.data[DOMAIN]["discovery"]
    try:
        result = await manager.adopt(msg.get("source_entry_id")) if msg["operation"] == "adopt" else await manager.scan()
        connection.send_result(msg["id"], result)
    except ValueError as exc:
        connection.send_error(msg["id"], "discovery_error", str(exc))
