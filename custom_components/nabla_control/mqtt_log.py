# Optional, read-only MQTT monitor. Persist settings, never message contents.
import asyncio
from collections import deque
from datetime import datetime, timezone
import time

from homeassistant.core import callback
from homeassistant.helpers.storage import Store


def validate_settings(data):
    topics = list(dict.fromkeys(t.strip() for t in data.get('topics', []) if t.strip()))
    if len(topics) > 8:
        raise ValueError('Use at most eight topic filters')
    for topic in topics:
        parts = topic.split('/')
        if len(topic.encode()) > 256 or '\x00' in topic or any(
            ('+' in p and p != '+') or ('#' in p and (p != '#' or i != len(parts)-1))
            for i, p in enumerate(parts)
        ):
            raise ValueError('Invalid MQTT topic filter')
    enabled = bool(data.get('enabled', False))
    limit = int(data.get('limit', 200))
    if not 50 <= limit <= 1000 or (enabled and not topics):
        raise ValueError('Select topics and a history size between 50 and 1000')
    return {'enabled': enabled, 'topics': topics, 'limit': limit}


class MessageBuffer:
    def __init__(self, limit=200):
        self.rows = deque(maxlen=limit)
        self.sequence = 0
        self.dropped = 0
        self.window = 0
        self.received = 0

    def append(self, message):
        now = int(time.monotonic())
        if now != self.window:
            self.window, self.received = now, 0
        self.received += 1
        if self.received > 100:
            self.dropped += 1
            return
        payload = message.payload
        if isinstance(payload, bytes):
            truncated = len(payload) > 2048
            payload = payload[:2048].decode('utf-8', errors='replace')
        else:
            truncated = len(payload) > 2048
            payload = payload[:2048]
        self.sequence += 1
        self.rows.append({'id': self.sequence, 'time': datetime.now(timezone.utc).isoformat(),
                          'topic': message.topic[:256], 'payload': payload,
                          'retain': bool(message.retain), 'qos': message.qos,
                          'truncated': truncated})

    def clear(self):
        self.rows.clear()
        self.dropped = 0


class MqttLog:
    def __init__(self, hass):
        self.hass = hass
        self.store = Store(hass, 1, 'nabla_control.mqtt_log')
        self.settings = validate_settings({})
        self.buffer = MessageBuffer()
        self.unsubscribers = []
        self.lock = asyncio.Lock()
        self.error = None

    async def restore(self):
        saved = await self.store.async_load()
        if saved:
            try:
                await self.configure(saved, persist=False)
            except (ValueError, TimeoutError, RuntimeError):
                self.settings = validate_settings(saved)
                self.error = 'MQTT unavailable. Check the HA MQTT integration and apply settings again.'

    @callback
    def receive(self, message):
        self.buffer.append(message)

    async def configure(self, data, persist=True):
        settings = validate_settings(data)
        async with self.lock:
            pending = []
            try:
                if settings['enabled']:
                    from homeassistant.components import mqtt
                    async with asyncio.timeout(10):
                        if not await mqtt.async_wait_for_mqtt_client(self.hass):
                            raise RuntimeError('Configure the MQTT integration first')
                        for topic in settings['topics']:
                            pending.append(await mqtt.async_subscribe(self.hass, topic, self.receive, qos=0, encoding=None))
                if persist:
                    await self.store.async_save(settings)
            except Exception as exc:
                for remove in pending:
                    remove()
                self.error = 'Unable to apply MQTT settings; previous settings are unchanged.'
                raise RuntimeError(self.error) from exc
            for remove in self.unsubscribers:
                remove()
            self.unsubscribers = pending
            self.settings = settings
            self.buffer = MessageBuffer(settings['limit'])
            self.error = None

    def snapshot(self):
        return {**self.settings, 'active': bool(self.unsubscribers), 'error': self.error,
                'dropped': self.buffer.dropped, 'rows': list(self.buffer.rows)}

    def stop(self):
        for remove in self.unsubscribers:
            remove()
        self.unsubscribers.clear()
        self.buffer.clear()
