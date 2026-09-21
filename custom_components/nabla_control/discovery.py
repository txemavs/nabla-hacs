"""Discover reachable Nabla endpoints already known to HA's ESPHome integration."""
import asyncio
from datetime import timedelta
import json

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .identity import normalize_host, http_host

DOMAIN = 'nabla_control'


class Discovery:
    """Explicit inventory search and opt-in address tracking; no subnet scans."""
    def __init__(self, hass):
        self.hass = hass
        self.gate = asyncio.Semaphore(4)
        self.lock = asyncio.Lock()
        self.scan_task = None
        self.closed = False
        self.remove_timer = async_track_time_interval(hass, self.reconcile, timedelta(seconds=60))

    def sources(self):
        result = {}
        for entry in self.hass.config_entries.async_entries('esphome'):
            if entry.disabled_by:
                continue
            try:
                host = normalize_host(entry.data.get('host', ''))
            except (ValueError, AttributeError):
                continue
            result[entry.entry_id] = {'source_entry_id': entry.entry_id,
                'host': host, 'name': entry.title}
        return result

    async def probe(self, host):
        session = async_get_clientsession(self.hass)
        async with self.gate:
            for path, kind in (('/mirror/capabilities', 'mirror'), ('/nabla/state', 'web')):
                try:
                    async with session.get(f'http://{http_host(host)}{path}',
                            timeout=aiohttp.ClientTimeout(total=2), allow_redirects=False) as response:
                        if response.status != 200:
                            continue
                        payload = bytearray()
                        async for chunk in response.content.iter_chunked(4096):
                            payload.extend(chunk)
                            if len(payload) > 16384:
                                break
                        if len(payload) > 16384:
                            continue
                        data = json.loads(payload)
                        if not isinstance(data, dict):
                            continue
                        if kind == 'mirror' and data.get('format') in ('mono1', 'rgb332') and all(
                                type(data.get(key)) is int and 1 <= data[key] <= 480 for key in ('width', 'height')):
                            return kind
                        if kind == 'web' and isinstance(data.get('nodes'), list) and (
                                type(data.get('camera_port')) is int and type(data.get('connected')) is bool):
                            return kind
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, UnicodeError):
                    continue
        return None

    async def scan(self):
        if self.closed:
            raise ValueError('Discovery is stopped')
        if self.scan_task is None or self.scan_task.done():
            self.scan_task = asyncio.create_task(self._scan())
        return await asyncio.shield(self.scan_task)

    async def _scan(self):
        sources = list(self.sources().values())
        found = []
        entries = self.hass.config_entries.async_entries(DOMAIN)
        async def check(source):
            kind = await self.probe(source['host'])
            if not kind:
                return
            linked = next((entry for entry in entries if entry.data.get('source_entry_id') == source['source_entry_id']), None)
            existing = linked or next((entry for entry in entries
                if entry.options.get('host', entry.data.get('host')) == source['host']), None)
            found.append({**source, 'kind': kind, 'configured': bool(existing), 'linked': bool(linked)})
        partial = len(sources) > 64
        try:
            async with asyncio.timeout(20):
                await asyncio.gather(*(check(source) for source in sources[:64]))
        except TimeoutError:
            partial = True
        return {'devices': sorted(found, key=lambda item: item['name'].casefold()),
                'known': len(sources), 'partial': partial}

    async def adopt(self, source_id):
        async with self.lock:
            source = self.sources().get(source_id)
            if not source or self.closed:
                raise ValueError('The ESPHome entry is no longer available')
            kind = await self.probe(source['host'])
            if not kind:
                raise ValueError('The device no longer responds as a Nabla endpoint')
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data.get('source_entry_id') == source_id:
                    return {'status': 'already_configured'}
                if entry.options.get('host', entry.data.get('host')) == source['host']:
                    if entry.data.get('source_entry_id'):
                        raise ValueError('This address is linked to another ESPHome entry')
                    self.hass.config_entries.async_update_entry(entry,
                        data={**entry.data, 'source_entry_id': source_id},
                        options={**entry.options, 'follow_source': True})
                    return {'status': 'linked'}
            result = await self.hass.config_entries.flow.async_init(DOMAIN,
                context={'source': 'integration_discovery'}, data={'source_entry_id': source_id})
            if result['type'] != 'create_entry':
                raise ValueError('Could not add the device; refresh the search')
            return {'status': 'added'}

    async def reconcile(self, _now=None):
        if self.closed or self.lock.locked():
            return
        async with self.lock:
            sources = self.sources()
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                source_id = entry.data.get('source_entry_id')
                settings = {**entry.data, **entry.options}
                source = sources.get(source_id)
                if entry.disabled_by or settings.get('follow_mqtt', False) or not source or not settings.get('follow_source', False):
                    continue
                host = source['host']
                if host == settings.get('host') or any(other.entry_id != entry.entry_id and
                        other.options.get('host', other.data.get('host')) == host
                        for other in self.hass.config_entries.async_entries(DOMAIN)):
                    continue
                if await self.probe(host) and not self.closed:
                    # The stable entry/device ID and dashboard references are retained.
                    self.hass.config_entries.async_update_entry(entry, options={**entry.options, 'host': host})

    async def close(self):
        self.closed = True
        self.remove_timer()
        if self.scan_task and not self.scan_task.done():
            self.scan_task.cancel()
            await asyncio.gather(self.scan_task, return_exceptions=True)
