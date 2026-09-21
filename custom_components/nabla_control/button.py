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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Nabla Control button entities."""
    devices = hass.data[DOMAIN]["devices"]

    entities = []
    for device_id, device in devices.items():
        if await _wait_for_capabilities(device):
            if device.has_input:
                for action, name, icon in ACTIONS:
                    entities.append(NablaControlButton(device, action, name, icon))
            else:
                _LOGGER.info("Device %s has no input, skipping buttons", device.name)

    async_add_entities(entities, update_before_add=False)


async def _wait_for_capabilities(device, timeout: float = 10.0) -> bool:
    """Wait for device capabilities to be fetched."""
    import asyncio

    for _ in range(int(timeout / 0.5)):
        if device.capabilities is not None:
            return True
        await asyncio.sleep(0.5)

    _LOGGER.warning("Timeout waiting for capabilities from %s", device.name)
    return False


class NablaControlButton(ButtonEntity):
    """Button entity for a Nabla Control encoder action."""

    def __init__(self, device, action: str, action_name: str, icon: str):
        self._device = device
        self._action = action
        self._attr_name = f"{device.name} {action_name}"
        self._attr_unique_id = f"nabla_control_{device.device_id}_{action}"
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        return self._device.available and self._device.has_input

    async def async_press(self) -> None:
        """Handle button press."""
        await self._device.send_action(self._action)
