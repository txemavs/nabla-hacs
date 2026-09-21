# UI configuration and one-time YAML import for independently reloadable devices.
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DeviceState, DOMAIN
from .camera import CAMERA_SCHEMA
from .identity import normalize_host, legacy_id


def schema(data):
    return vol.Schema({
        vol.Required("host", default=data.get("host", "")): str,
        vol.Optional("name", default=data.get("name", "Nabla device")): str,
        vol.Optional("follow_source", default=data.get("follow_source", False)): bool,
        vol.Optional("follow_mqtt", default=data.get("follow_mqtt", False)): bool,
        vol.Optional("kind", default=data.get("kind", "auto")): vol.In(["auto", "mirror", "web"]),
        vol.Optional("poll_interval", default=data.get("poll_interval", 1.0)):
            vol.All(vol.Coerce(float), vol.Range(min=0.2, max=30)),
    })


def duplicate_host(hass, host, exclude=None):
    return any(
        e.data.get("entry_type") != "camera_cache" and e.entry_id != exclude and normalize_host(e.options.get("host", e.data["host"])) == host
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
        return self.async_show_menu(step_id="user", menu_options=["device", "camera_cache"])

    async def async_step_device(self, user_input=None):
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
        return self.async_show_form(step_id="device", data_schema=schema(user_input or {}), errors=errors)

    async def async_step_integration_discovery(self, discovery_info):
        if "mqtt_identity" in discovery_info:
            identity = discovery_info["mqtt_identity"]
            manager = self.hass.data[DOMAIN]["mqtt_presence"]
            row = manager.rows.get(identity)
            kind = await manager.verify(row) if row else None
            if not kind:
                return self.async_abort(reason="cannot_connect")
            await self.async_set_unique_id("mqtt:" + identity)
            self._abort_if_unique_id_configured()
            if duplicate_host(self.hass, row["host"]):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(title=row["name"], data={
                "host": row["host"], "name": row["name"], "mqtt_identity": identity,
                "device_id": uuid4().hex, "kind": kind, "poll_interval": 1.0,
                "follow_mqtt": True, "follow_source": False})
        source_id = discovery_info["source_entry_id"]
        manager = self.hass.data[DOMAIN]["discovery"]
        source = manager.sources().get(source_id)
        if not source:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id("esphome:" + source_id)
        self._abort_if_unique_id_configured()
        if duplicate_host(self.hass, source["host"]):
            return self.async_abort(reason="already_configured")
        kind = await manager.probe(source["host"])
        if not kind:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(title=source["name"], data={**source,
            "device_id": uuid4().hex, "kind": kind, "poll_interval": 1.0, "follow_source": True})

    async def async_step_import(self, user_input):
        if user_input.get("entry_type") == "camera_cache":
            return await self.async_step_camera_cache({k: v for k, v in user_input.items() if k != "entry_type"})
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

    async def async_step_camera_cache(self, user_input=None):
        await self.async_set_unique_id("camera_cache")
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            try:
                data = CAMERA_SCHEMA(user_input)
                return self.async_create_entry(title="Camera Cache", data={"entry_type": "camera_cache", **data})
            except vol.Invalid:
                errors["base"] = "invalid_camera_settings"
        return self.async_show_form(step_id="camera_cache", data_schema=camera_schema(user_input or {}), errors=errors)


class NablaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        defaults = {**self.config_entry.data, **self.config_entry.options}
        if defaults.get("entry_type") == "camera_cache":
            if user_input is not None:
                try:
                    return self.async_create_entry(title="", data=CAMERA_SCHEMA(user_input))
                except vol.Invalid:
                    errors["base"] = "invalid_camera_settings"
            return self.async_show_form(step_id="init", data_schema=camera_schema(user_input or defaults), errors=errors)
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


def camera_schema(data):
    return vol.Schema({
        vol.Required("cameras", default=data.get("cameras", [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="camera", multiple=True)),
        vol.Optional("refresh_interval", default=data.get("refresh_interval", 1.0)): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=60)),
        vol.Optional("max_stale", default=data.get("max_stale", 8.0)): vol.All(vol.Coerce(float), vol.Range(min=1, max=60)),
        vol.Optional("quality", default=data.get("quality", 70)): vol.All(vol.Coerce(int), vol.Range(min=30, max=85)),
    })
