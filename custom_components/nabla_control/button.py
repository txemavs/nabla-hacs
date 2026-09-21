# Button entities for Nabla Control encoder actions.
# Only created when the device actually exposes input (encoder), not for web/touch.

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

DOMAIN = "nabla_control"

_LOGGER = logging.getLogger(__name__)

ACTIONS = [
    ("up", "Up", "mdi:arrow-up"),
    ("down", "Down", "mdi:arrow-down"),
    ("enter", "Enter", "mdi:check"),
    ("back", "Back", "mdi:arrow-left"),
]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Create encoder buttons only when the device reports input capability."""
    device = hass.data[DOMAIN]["entries"][entry.entry_id]

    # Configured web/touch devices never get encoder button entities.
    if entry.data.get("kind") == "web":
        _LOGGER.debug("Skipping encoder buttons for web device %s", device.name)
        return

    # Resolve capabilities before deciding (auto/mirror).
    if device.kind is None or device.capabilities is None:
        discover = getattr(device, "_discover_kind", None) or getattr(
            device, "async_discover", None
        )
        if discover is not None:
            try:
                await discover()
            except Exception as err:  # noqa: BLE001 — discovery best-effort
                _LOGGER.debug("Discover before buttons failed for %s: %s", device.name, err)

    if device.kind == "web" or not device.has_input:
        _LOGGER.debug(
            "No encoder buttons for %s (kind=%s has_input=%s)",
            device.name,
            device.kind,
            getattr(device, "has_input", False),
        )
        return

    async_add_entities(
        [
            NablaControlButton(device, action, name, icon)
            for action, name, icon in ACTIONS
        ]
    )


class NablaControlButton(ButtonEntity):
    """Button entity for a Nabla Control encoder action."""

    _attr_has_entity_name = True

    def __init__(self, device, action: str, action_name: str, icon: str):
        self._device = device
        self._action = action
        self._attr_name = action_name
        self._attr_unique_id = f"nabla_control_{device.device_id}_{action}"
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": "Nabla",
        }

    @property
    def available(self) -> bool:
        # Offline mirror with input → unavailable is correct.
        # Web/touch should not create these entities at all.
        return bool(self._device.available and self._device.has_input)

    async def async_press(self) -> None:
        """Handle button press."""
        send = getattr(self._device, "send_action", None) or getattr(
            self._device, "async_send_action", None
        )
        if send is None:
            _LOGGER.error("Device %s has no send_action", self._device.name)
            return
        await send(self._action)


async def async_remove_orphan_encoder_buttons(hass, device_id: str) -> int:
    """Remove registry entries for encoder buttons of a device without input."""
    registry = async_get_entity_registry(hass)
    removed = 0
    prefix = f"nabla_control_{device_id}_"
    for action, _, _ in ACTIONS:
        uid = f"{prefix}{action}"
        entry = registry.async_get_entity_id("button", DOMAIN, uid)
        if entry:
            registry.async_remove(entry)
            removed += 1
    return removed
