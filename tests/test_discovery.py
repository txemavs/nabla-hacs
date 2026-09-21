"""Inventory discovery and address-following regression tests at the HA boundary."""
import asyncio
from datetime import timedelta
import json
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock
import aiohttp
from test_dynamic_devices import load_code, identity


class DiscoveryTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.source=NS(entry_id='source1',disabled_by=None,title='Panel',data={'host':'192.0.2.10'})
        self.device=NS(entry_id='control1',disabled_by=None,title='Panel',data={
            'host':'192.0.2.10','device_id':'stable-id'},options={})
        self.sources=[self.source];self.devices=[self.device]
        self.hass=NS(config_entries=NS(async_entries=lambda domain:self.sources if domain=='esphome' else self.devices,
            async_update_entry=Mock(),flow=NS(async_init=AsyncMock(return_value={'type':'create_entry'}))))
        self.ns=load_code('discovery.py',{'Discovery'},dict(asyncio=asyncio,timedelta=timedelta,json=json,
            aiohttp=aiohttp,DOMAIN='nabla_control',normalize_host=identity.normalize_host,http_host=identity.http_host,
            async_track_time_interval=lambda *args:Mock(),async_get_clientsession=lambda hass:self.session))
        self.manager=self.ns['Discovery'](self.hass)
        self.manager.probe=AsyncMock(return_value='mirror')

    async def asyncTearDown(self):await self.manager.close()

    async def test_inventory_ignores_disabled_invalid_hosts(self):
        self.sources += [NS(entry_id='bad',disabled_by=None,data={'host':'http://bad'}),
                         NS(entry_id='off',disabled_by='user')]
        self.assertEqual(list(self.manager.sources()),['source1'])

    async def test_scan_does_not_change_entries(self):
        result=await self.manager.scan()
        self.assertEqual(result['devices'][0]['configured'],True)
        self.assertEqual(result['devices'][0]['linked'],False)
        self.hass.config_entries.async_update_entry.assert_not_called()

    async def test_scan_shared_between_concurrent_clients(self):
        await asyncio.gather(*(self.manager.scan() for _ in range(10)))
        self.manager.probe.assert_awaited_once()

    async def test_bind_existing_preserves_device_id(self):
        self.assertEqual(await self.manager.adopt('source1'),{'status':'linked'})
        kwargs=self.hass.config_entries.async_update_entry.call_args.kwargs
        self.assertEqual(kwargs['data']['device_id'],'stable-id')
        self.assertTrue(kwargs['options']['follow_source'])
        self.hass.config_entries.flow.async_init.assert_not_awaited()

    async def test_add_new_uses_flow(self):
        self.devices.clear()
        self.assertEqual(await self.manager.adopt('source1'),{'status':'added'})
        self.hass.config_entries.flow.async_init.assert_awaited_once()

    async def test_removed_or_offline_source_cannot_be_adopted(self):
        with self.assertRaises(ValueError):await self.manager.adopt('missing')
        self.manager.probe.return_value=None
        with self.assertRaises(ValueError):await self.manager.adopt('source1')
        self.hass.config_entries.async_update_entry.assert_not_called()

    def link(self):
        self.device.data.update(source_entry_id='source1',follow_source=True)
        self.source.data['host']='198.51.100.20'

    async def test_changed_address_updates_only_options(self):
        self.link();await self.manager.reconcile()
        self.hass.config_entries.async_update_entry.assert_called_once_with(self.device,options={'host':'198.51.100.20'})
        self.assertEqual(self.device.data['device_id'],'stable-id')

    async def test_no_change_means_no_network_probe(self):
        self.link();self.source.data['host']='192.0.2.10'
        await self.manager.reconcile();self.manager.probe.assert_not_awaited()

    async def test_manual_opt_out_and_invalid_destination_keep_address(self):
        self.link();self.device.options['follow_source']=False
        await self.manager.reconcile();self.manager.probe.assert_not_awaited()
        self.device.options['follow_source']=True;self.manager.probe.return_value=None
        await self.manager.reconcile();self.hass.config_entries.async_update_entry.assert_not_called()

    async def test_collision_does_not_steal_other_device(self):
        self.link();self.devices.append(NS(entry_id='other',disabled_by=None,data={'host':'198.51.100.20'},options={}))
        await self.manager.reconcile();self.hass.config_entries.async_update_entry.assert_not_called()

    async def test_probe_checks_actual_protocol_and_size(self):
        class Response:
            status=200
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            @property
            def content(self):return self
            async def iter_chunked(self,size):
                yield self.payload[:5];yield self.payload[5:]
        response=Response();self.session=NS(get=lambda *a,**kw:response)
        probe=self.ns['Discovery'].probe
        response.payload=json.dumps({'width':160,'height':128,'format':'rgb332'}).encode()
        self.assertEqual(await probe(self.manager,'192.0.2.10'),'mirror')
        response.payload=json.dumps({'nodes':[],'camera_port':8080,'connected':True}).encode()
        self.assertEqual(await probe(self.manager,'192.0.2.10'),'web')
        response.payload=b'{}';self.assertIsNone(await probe(self.manager,'192.0.2.10'))
        response.payload=b' ' * 17000;self.assertIsNone(await probe(self.manager,'192.0.2.10'))
