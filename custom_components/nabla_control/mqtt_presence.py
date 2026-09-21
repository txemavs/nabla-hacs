"""Opt-in, bounded MQTT address discovery; HTTP confirms identity before adoption."""
import asyncio
from datetime import timedelta
import ipaddress
import json
import re
import time

import aiohttp
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from .identity import http_host

DOMAIN = 'nabla_control'


def settings_for(data):
    prefix = data.get('topic_prefix', 'nabla/discovery')
    if not isinstance(prefix, str) or len(prefix) > 128 or not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', prefix):
        raise ValueError('Invalid discovery topic prefix')
    return {'enabled': bool(data.get('enabled', False)), 'topic_prefix': prefix}


def parse_announcement(topic, payload, prefix):
    if len(payload) > 1024:
        raise ValueError('Announcement too large')
    data = json.loads(payload)
    if not isinstance(data, dict) or type(data.get('v')) is not int or data['v'] != 1:
        raise ValueError('Unsupported announcement')
    identity = data.get('device_id', '')
    boot = data.get('boot_id', '')
    if not isinstance(identity, str) or not re.fullmatch(r'esp32-[0-9a-f]{12}', identity):
        raise ValueError('Invalid identity')
    if topic != f'{prefix}/{identity}/announce' or not isinstance(boot, str) or not re.fullmatch(r'[0-9a-f]{16}', boot):
        raise ValueError('Invalid topic or boot identity')
    host = ipaddress.ip_address(data.get('host', ''))
    if host.version != 4 or host.is_loopback or host.is_link_local or host.is_multicast or host.is_unspecified or host.is_reserved:
        raise ValueError('Invalid unicast IPv4 address')
    name = data.get('name', identity)
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid name')
    return {'device_id': identity, 'boot_id': boot, 'host': str(host), 'name': name}


class MqttPresence:
    def __init__(self, hass, discovery):
        self.hass, self.discovery = hass, discovery
        self.store = Store(hass, 1, 'nabla_control.mqtt_presence')
        self.settings = settings_for({})
        self.rows = {}
        self.remove = None
        self.error = None
        self.closed = False
        self.lock = asyncio.Lock()
        self.config_lock = asyncio.Lock()
        self.generation = 0
        self.cursor = 0
        self.remove_timer = async_track_time_interval(hass, self.reconcile, timedelta(seconds=15))

    async def restore(self):
        saved = await self.store.async_load()
        if saved:
            try:
                await self.configure(saved, persist=False)
            except (ValueError, RuntimeError):
                self.error = 'MQTT discovery unavailable; apply settings again after MQTT is ready.'

    async def configure(self, data, persist=True):
        settings = settings_for(data)
        async with self.config_lock:
            remove = None
            generation = self.generation + 1
            def receive(message):
                if generation == self.generation:
                    self.receive(message)
            try:
                if settings['enabled']:
                    from homeassistant.components import mqtt
                    async with asyncio.timeout(10):
                        if not await mqtt.async_wait_for_mqtt_client(self.hass):
                            raise RuntimeError('Configure the HA MQTT integration first')
                        remove = await mqtt.async_subscribe(self.hass,
                            settings['topic_prefix'] + '/+/announce', receive, qos=1, encoding=None)
                if persist:
                    await self.store.async_save(settings)
            except Exception as exc:
                if remove:
                    remove()
                raise RuntimeError('Could not apply MQTT discovery settings') from exc
            self.generation = generation
            if self.remove:
                self.remove()
            self.remove = remove
            self.settings = settings
            self.rows.clear()
            self.error = None

    @callback
    def receive(self, message):
        if self.closed or not self.settings['enabled']:
            return
        try:
            row = parse_announcement(message.topic, message.payload, self.settings['topic_prefix'])
        except (ValueError, TypeError, UnicodeError):
            return
        now = time.monotonic()
        self.prune(now)
        identity = row['device_id']
        if identity not in self.rows and len(self.rows) >= 64:
            return
        # Messages are hints, including retained messages. They never set availability.
        self.rows[identity] = {**row, 'seen': now}

    def prune(self, now=None):
        now = time.monotonic() if now is None else now
        self.rows = {key: row for key, row in self.rows.items() if now - row['seen'] <= 180}

    def current(self, row):
        latest = self.rows.get(row['device_id'])
        return not self.closed and self.settings['enabled'] and latest == row and time.monotonic() - row['seen'] <= 180

    def entries(self):
        return [e for e in self.hass.config_entries.async_entries(DOMAIN)
                if e.data.get('entry_type') != 'camera_cache']

    async def verify(self, row):
        if not self.current(row):
            return None
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(f"http://{http_host(row['host'])}/nabla/identity",
                    timeout=aiohttp.ClientTimeout(total=2), allow_redirects=False) as response:
                if response.status != 200:
                    return None
                payload = bytearray()
                async for chunk in response.content.iter_chunked(1024):
                    payload.extend(chunk)
                    if len(payload) > 1024:
                        return None
                identity = json.loads(payload)
            if not isinstance(identity, dict) or type(identity.get('v')) is not int or identity.get('v') != 1 or any(
                    identity.get(key) != row[key] for key in ('device_id', 'boot_id')):
                return None
            kind = await self.discovery.probe(row['host'])
            return kind if self.current(row) else None
        except (aiohttp.ClientError, TimeoutError, ValueError, UnicodeError):
            return None

    async def bind(self, identity, entry_id):
        async with self.lock, self.discovery.lock:
            self.prune()
            row = self.rows.get(identity)
            if not row or not await self.verify(row):
                raise ValueError('The announced device does not confirm its identity over HTTP')
            entries = self.entries()
            if not entry_id:
                if any(e.data.get('mqtt_identity') == identity or e.options.get('host', e.data.get('host')) == row['host'] for e in entries):
                    raise ValueError('This device already exists; select its entry to link it')
                result = await self.hass.config_entries.flow.async_init(DOMAIN,
                    context={'source': 'integration_discovery'}, data={'mqtt_identity': identity})
                if result['type'] != 'create_entry':
                    raise ValueError('Could not add the MQTT device; refresh announcements')
                return {'added': True}
            entry = next((e for e in entries if e.entry_id == entry_id), None)
            if not entry or entry.disabled_by:
                raise ValueError('Select an existing Nabla Control device')
            if any(e.entry_id != entry_id and (e.data.get('mqtt_identity') == identity or
                   e.options.get('host', e.data.get('host')) == row['host']) for e in entries):
                raise ValueError('Identity or address already belongs to another device')
            if entry.data.get('mqtt_identity') not in (None, identity):
                raise ValueError('This device is already linked to another MQTT identity')
            self.hass.config_entries.async_update_entry(entry,
                data={**entry.data, 'mqtt_identity': identity},
                options={**entry.options, 'host': row['host'], 'follow_mqtt': True, 'follow_source': False})
            return {'linked': True}

    async def reconcile(self, _now=None):
        if self.closed or not self.settings['enabled'] or self.lock.locked():
            return
        async with self.lock, self.discovery.lock:
            self.prune()
            # Bound network work per timer tick; next tick continues where needed.
            probes = 0
            entries = self.entries()
            start = self.cursor % max(1, len(entries))
            entries = entries[start:] + entries[:start]
            for entry in entries:
                settings = {**entry.data, **entry.options}
                row = self.rows.get(entry.data.get('mqtt_identity'))
                if entry.disabled_by or not settings.get('follow_mqtt') or not row or row['host'] == settings.get('host'):
                    continue
                if any(e.entry_id != entry.entry_id and e.options.get('host', e.data.get('host')) == row['host'] for e in self.entries()):
                    continue
                if probes >= 4:
                    break
                probes += 1
                self.cursor += 1
                if await self.verify(row) and not entry.disabled_by and entry.data.get('mqtt_identity') == row['device_id'] and {
                        **entry.data, **entry.options} == settings and not any(
                        e.entry_id != entry.entry_id and e.options.get('host', e.data.get('host')) == row['host'] for e in self.entries()):
                    self.hass.config_entries.async_update_entry(entry,
                        options={**entry.options, 'host': row['host']})

    def snapshot(self):
        self.prune()
        entries = self.entries()
        return {**self.settings, 'active': self.remove is not None, 'error': self.error,
            'devices': [{'entry_id': e.entry_id, 'name': e.title,
                         'identity': e.data.get('mqtt_identity'),
                         'disabled': bool(e.disabled_by),
                         'following': e.options.get('follow_mqtt', e.data.get('follow_mqtt', False))} for e in entries],
            'announcements': [{k: v for k, v in row.items() if k not in ('seen', 'boot_id')} for row in self.rows.values()]}

    async def close(self):
        self.closed = True
        self.generation += 1
        self.remove_timer()
        if self.remove:
            self.remove()
            self.remove = None
        self.rows.clear()
