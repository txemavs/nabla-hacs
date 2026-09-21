# Button entities for Nabla Control encoder actions.
# Creates up/down/enter/back buttons for devices with input capability.

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "nabla_control"

_LOGGER = logging.getLogger(__name__)

ACTIONS = [
    ("up", "Up", "mdi:arrow-up"),
    ("down", "Down", "mdi:arrow-down"),
    ("enter", "Enter", "mdi:check"),
    ("back", "Back", "mdi:arrow-left"),
]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Create controls immediately; availability follows negotiated capability."""
    device = hass.data[DOMAIN]["entries"][entry.entry_id]
    async_add_entities([
        NablaControlButton(device, action, name, icon)
        for action, name, icon in ACTIONS
    ])


class NablaControlButton(ButtonEntity):
    """Button entity for a Nabla Control encoder action."""

    def __init__(self, device, action: str, action_name: str, icon: str):
        self._device = device
        self._action = action
        self._attr_name = f"{device.name} {action_name}"
        self._attr_unique_id = f"nabla_control_{device.device_id}_{action}"
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": "Nabla",
        }

    @property
    def available(self) -> bool:
        return self._device.available and self._device.has_input

    async def async_press(self) -> None:
        """Handle button press."""
        await self._device.send_action(self._action)
