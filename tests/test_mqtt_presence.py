"""Exercise MQTT hints, live identity confirmation and stable entry updates."""
import asyncio
from datetime import timedelta
import ipaddress
import json
import re
import time
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, AsyncMock
import aiohttp
from test_dynamic_devices import load_code, identity

NS_CODE = dict(asyncio=asyncio, timedelta=timedelta, ipaddress=ipaddress, json=json, re=re, time=time,
    aiohttp=aiohttp, DOMAIN='nabla_control', callback=lambda f:f, http_host=identity.http_host,
    Store=lambda *a:NS(async_load=AsyncMock(return_value=None), async_save=AsyncMock()),
    async_track_time_interval=lambda *a:Mock())
load_code('mqtt_presence.py', {'settings_for','parse_announcement','MqttPresence'}, NS_CODE)
parse = NS_CODE['parse_announcement']
PREFIX = 'nabla/discovery'
ID = 'esp32-001122aabbcc'
BOOT = '0123456789abcdef'


def message(**changes):
    data = dict(v=1, device_id=ID, boot_id=BOOT, host='192.0.2.20', name='Test panel')
    data.update(changes)
    return NS(topic=f'{PREFIX}/{ID}/announce', payload=json.dumps(data).encode(), retain=True)


class ParserTests(TestCase):
    def test_valid_retained_hint(self):
        m=message();self.assertEqual(parse(m.topic,m.payload,PREFIX)['host'],'192.0.2.20')

    def test_reject_malformed_and_unsafe_destinations(self):
        for changes in [dict(v=True),dict(v=2),dict(device_id='bad'),dict(boot_id='bad'),
                        dict(host='http://host'),dict(host='127.0.0.1'),dict(host='169.254.169.254'),
                        dict(host='224.0.0.1'),dict(host='0.0.0.0'),dict(host='::1'),dict(name='x'*65)]:
            m=message(**changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):parse(m.topic,m.payload,PREFIX)
        m=message()
        with self.assertRaises(ValueError):parse('other/topic',m.payload,PREFIX)
        with self.assertRaises(ValueError):parse(m.topic,b'x'*1025,PREFIX)

    def test_prefix_rejects_wildcards(self):
        for prefix in ['#','x/+', '/x','x/', 'x//y', 'x'*129]:
            with self.assertRaises(ValueError):NS_CODE['settings_for']({'topic_prefix':prefix})


class PresenceTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.entry=NS(entry_id='e1',title='Panel',disabled_by=None,
            data={'device_id':'stable-ui-id','host':'192.0.2.10','mqtt_identity':ID}, options={'follow_mqtt':True})
        self.entries=[self.entry]
        def update(entry,**kw):
            for k,v in kw.items():setattr(entry,k,v)
        self.hass=NS(config_entries=NS(async_entries=lambda d:self.entries,
            async_update_entry=Mock(side_effect=update),flow=NS(async_init=AsyncMock(return_value={'type':'create_entry'}))))
        self.discovery=NS(lock=asyncio.Lock(),probe=AsyncMock(return_value='mirror'))
        NS_CODE['async_get_clientsession']=lambda h:self.session
        self.manager=NS_CODE['MqttPresence'](self.hass,self.discovery)
        self.manager.settings={'enabled':True,'topic_prefix':PREFIX}
        self.manager.receive(message())
        self.real_verify=self.manager.verify
        self.manager.verify=AsyncMock(return_value='mirror')

    async def asyncTearDown(self):await self.manager.close()

    async def test_follow_changes_only_host_and_keeps_identity(self):
        await self.manager.reconcile()
        self.assertEqual(self.entry.options['host'],'192.0.2.20')
        self.assertEqual(self.entry.data['device_id'],'stable-ui-id')
        await self.manager.reconcile()
        self.manager.verify.assert_awaited_once()

    async def test_optout_disabled_stale_collision_and_unreachable(self):
        for variant in ['optout','disabled','stale','collision','unreachable']:
            with self.subTest(variant=variant):
                self.entry.options={'follow_mqtt':variant!='optout'}
                self.entry.disabled_by='user' if variant=='disabled' else None
                self.manager.receive(message())
                self.manager.rows[ID]['seen']=time.monotonic()-181 if variant=='stale' else time.monotonic()
                self.entries[:]=[self.entry]
                if variant=='collision':self.entries.append(NS(entry_id='other',disabled_by=None,data={'host':'192.0.2.20'},options={}))
                self.manager.verify.return_value=None if variant=='unreachable' else 'mirror'
                await self.manager.reconcile()
                self.hass.config_entries.async_update_entry.assert_not_called()

    async def test_binding_is_explicit_and_preserves_old_entry(self):
        self.entry.data.pop('mqtt_identity');self.entry.options={}
        await self.manager.reconcile();self.manager.verify.assert_not_awaited()
        await self.manager.bind(ID,'e1')
        self.assertEqual(self.entry.data['device_id'],'stable-ui-id')
        self.assertEqual(self.entry.data['mqtt_identity'],ID)
        self.assertFalse(self.entry.options['follow_source'])
        self.assertTrue(self.entry.options['follow_mqtt'])

    async def test_cannot_bind_other_identity_or_duplicate_address(self):
        self.entry.data['mqtt_identity']='esp32-ffeeddccbbaa'
        with self.assertRaises(ValueError):await self.manager.bind(ID,'e1')
        self.entry.options['host']='192.0.2.20'
        with self.assertRaises(ValueError):await self.manager.bind(ID,'')

    async def test_new_device_uses_config_flow(self):
        self.entries.clear()
        self.assertEqual(await self.manager.bind(ID,''),{'added':True})
        self.hass.config_entries.flow.async_init.assert_awaited_once()

    async def test_no_update_when_user_opts_out_during_probe(self):
        async def verify(row):
            self.entry.options={'follow_mqtt':False}
            return 'mirror'
        self.manager.verify=verify
        await self.manager.reconcile()
        self.hass.config_entries.async_update_entry.assert_not_called()

    def test_bounded_inventory_and_expiry(self):
        for n in range(100):
            m=message(device_id=f'esp32-{n:012x}');m.topic=f'{PREFIX}/esp32-{n:012x}/announce'
            self.manager.receive(m)
        self.assertEqual(len(self.manager.rows),64)
        self.manager.prune(time.monotonic()+181)
        self.assertFalse(self.manager.rows)

    async def test_http_checks_boot_identity_not_only_capabilities(self):
        class Response:
            status=200
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            @property
            def content(self):return self
            async def iter_chunked(self,n):yield self.payload
        response=Response()
        self.session=NS(get=Mock(return_value=response))
        row=self.manager.rows[ID]
        response.payload=json.dumps(dict(v=1,device_id=ID,boot_id=BOOT)).encode()
        self.assertEqual(await self.real_verify(row),'mirror')
        self.assertFalse(self.session.get.call_args.kwargs['allow_redirects'])
        for payload in [b'{}', b'x'*1025, json.dumps(dict(v=1,device_id=ID,boot_id='0'*16)).encode()]:
            response.payload=payload
            self.assertIsNone(await self.real_verify(row))
        self.manager.rows[ID]={**row,'host':'192.0.2.21'}
        self.assertIsNone(await self.real_verify(row))

    async def test_disabled_subscription_does_not_receive(self):
        await self.manager.configure({'enabled':False})
        self.manager.receive(message());self.assertFalse(self.manager.rows)

    async def test_subscription_is_optional_and_replaced_cleanly(self):
        import sys
        from unittest.mock import patch
        removes=[]
        callbacks=[]
        async def subscribe(hass,topic,receive,**kwargs):
            self.assertEqual(topic,'nabla/discovery/+/announce')
            self.assertEqual(kwargs,{'qos':1,'encoding':None})
            remove=Mock();removes.append(remove);callbacks.append(receive);return remove
        mqtt=NS(async_wait_for_mqtt_client=AsyncMock(return_value=True),async_subscribe=subscribe)
        with patch.dict(sys.modules,{'homeassistant.components':NS(mqtt=mqtt)}):
            await self.manager.configure({'enabled':True})
            callbacks[0](message());self.assertIn(ID,self.manager.rows)
            await self.manager.configure({'enabled':True})
            removes[0].assert_called_once()
            callbacks[0](message());self.assertNotIn(ID,self.manager.rows)
            callbacks[1](message());self.assertIn(ID,self.manager.rows)
            await self.manager.configure({'enabled':False})
            removes[1].assert_called_once()
            callbacks[1](message());self.assertFalse(self.manager.rows)

    async def test_disable_during_identity_check_cannot_change_address(self):
        async def verify(row):
            await self.manager.configure({'enabled':False})
            return None
        self.manager.verify=verify
        await self.manager.reconcile()
        self.hass.config_entries.async_update_entry.assert_not_called()

    async def test_http_boot_check_expired_by_new_announcement(self):
        class Response:
            status=200
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            @property
            def content(self):return self
            async def iter_chunked(self,n):yield json.dumps(dict(v=1,device_id=ID,boot_id=BOOT)).encode()
        self.session=NS(get=Mock(return_value=Response()))
        async def probe(host):
            self.manager.receive(message(host='192.0.2.22'))
            return 'mirror'
        self.discovery.probe=probe
        self.assertIsNone(await self.real_verify(self.manager.rows[ID]))
