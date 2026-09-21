# UI configuration and one-time YAML import for independently reloadable devices.
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DeviceState, DOMAIN
from .identity import normalize_host, legacy_id


def schema(data):
    return vol.Schema({
        vol.Required("host", default=data.get("host", "")): str,
        vol.Optional("name", default=data.get("name", "Nabla device")): str,
        vol.Optional("kind", default=data.get("kind", "auto")): vol.In(["auto", "mirror", "web"]),
        vol.Optional("poll_interval", default=data.get("poll_interval", 1.0)):
            vol.All(vol.Coerce(float), vol.Range(min=0.2, max=30)),
    })


def duplicate_host(hass, host, exclude=None):
    return any(
        e.entry_id != exclude and normalize_host(e.options.get("host", e.data["host"])) == host
        for e in hass.config_entries.async_entries(DOMAIN)
    )


async def probe(hass, data):
    device = DeviceState(data["host"], data["name"], data["poll_interval"],
                         async_get_clientsession(hass), kind=data["kind"])
    return await device._discover_kind()


class NablaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NablaOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            try:
                data["host"] = normalize_host(data["host"])
                if duplicate_host(self.hass, data["host"]):
                    return self.async_abort(reason="already_configured")
                self._async_abort_entries_match({"host": data["host"]})
                if await probe(self.hass, data):
                    data["device_id"] = uuid4().hex
                    await self.async_set_unique_id(data["device_id"])
                    return self.async_create_entry(title=data["name"], data=data)
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["host"] = "invalid_host"
        return self.async_show_form(step_id="user", data_schema=schema(user_input or {}), errors=errors)

    async def async_step_import(self, user_input):
        data = dict(user_input)
        original_host = data["host"]
        data["host"] = normalize_host(original_host)
        # Persist the original import key: old YAML must not resurrect duplicates
        # after an options change updates the current endpoint.
        imported_id = legacy_id(original_host)
        await self.async_set_unique_id(imported_id)
        self._abort_if_unique_id_configured()
        if duplicate_host(self.hass, data["host"]):
            return self.async_abort(reason="already_configured")
        data["device_id"] = imported_id
        data.setdefault("name", f"Nabla Control {original_host}")
        data.setdefault("kind", "auto")
        data.setdefault("poll_interval", 1.0)
        return self.async_create_entry(title=data["name"], data=data)


class NablaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        defaults = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            data = dict(user_input)
            try:
                data["host"] = normalize_host(data["host"])
                if duplicate_host(self.hass, data["host"], self.config_entry.entry_id):
                    errors["host"] = "already_configured"
                elif data["host"] == defaults["host"] or await probe(self.hass, data):
                    return self.async_create_entry(title="", data=data)
                else:
                    errors["base"] = "cannot_connect"
            except ValueError:
                errors["host"] = "invalid_host"
        return self.async_show_form(step_id="init", data_schema=schema(user_input or defaults), errors=errors)
