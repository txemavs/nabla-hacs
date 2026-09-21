"""Diagnostics support for Nabla Control."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN, DeviceState

TO_REDACT = {"host", "camera_url", "web_url", "open_url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: dict[str, Any] = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
    }

    if entry.data.get("entry_type") == "camera_cache":
        cache_manager = hass.data[DOMAIN].get("camera_cache")
        if cache_manager:
            data["camera_cache"] = {
                "configured_cameras": len(cache_manager.caches),
                "cameras": [
                    {
                        "entity_id": entity_id,
                        "generations": cache.generations,
                        "failures": cache.failures,
                        "interval": cache.interval,
                    }
                    for entity_id, cache in cache_manager.caches.items()
                ],
            }
        return data

    device: DeviceState | None = hass.data[DOMAIN].get("entries", {}).get(
        entry.entry_id
    )
    if device:
        data["device"] = _device_diagnostics(device)

    return data


def _device_diagnostics(device: DeviceState) -> dict[str, Any]:
    """Extract diagnostic info from a device, redacting sensitive data."""
    return {
        "device_id": device.device_id,
        "name": device.name,
        "configured_kind": device.configured_kind,
        "resolved_kind": device.kind,
        "poll_interval": device.poll_interval,
        "available": device.available,
        "width": device.width,
        "height": device.height,
        "format": device.format,
        "has_input": device.has_input,
        "has_touch": device.has_touch,
        "has_camera": device.has_camera,
        "capabilities_from_fallback": device.capabilities_from_fallback,
        "polling_active": device.poll_task is not None
        and not device.poll_task.done(),
    }
