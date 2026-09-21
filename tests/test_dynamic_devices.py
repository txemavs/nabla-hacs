# Regression tests execute production flow/lifecycle code with a minimal HA boundary.
import ast
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/nabla_control'
spec = importlib.util.spec_from_file_location('identity', ROOT/'identity.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def load_code(filename, names, namespace):
    tree = ast.parse((ROOT/filename).read_text())
    tree.body = [n for n in tree.body if getattr(n, 'name', None) in names]
    exec(compile(tree, filename, 'exec'), namespace)
    return namespace


class IdentityTests(TestCase):
    def test_addresses(self):
        for source, expected in [(' PANEL.LOCAL. ', 'panel.local'), ('192.0.2.7','192.0.2.7'), ('[2001:db8::1]','2001:db8::1')]:
            self.assertEqual(identity.normalize_host(source), expected)
        self.assertEqual(identity.http_host('2001:db8::1'),'[2001:db8::1]')

    def test_reject_urls_credentials_ports(self):
        for value in ['http://panel', 'user:password@panel', 'panel/path', 'panel:80', '', '-bad.local']:
            with self.assertRaises(ValueError): identity.normalize_host(value)

    def test_migration_preserves_card_id(self):
        self.assertEqual(identity.legacy_id('192.0.2.7'),'192_0_2_7')


class LifecycleTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = {'devices':{},'entries':{}}
        self.hass = NS(data={'nabla_control':self.registry}, config_entries=NS(
            async_forward_entry_setups=AsyncMock(), async_unload_platforms=AsyncMock(return_value=True), async_reload=AsyncMock()))
        def device(host,name,interval,session,kind,device_id):
            return NS(host=host, device_id=device_id, start_polling=Mock(), stop_polling=AsyncMock())
        self.code = load_code('__init__.py', {'async_setup_entry','async_unload_entry','_async_update_entry'}, dict(
            DOMAIN='nabla_control', CONF_HOST='host', CONF_NAME='name', CONF_KIND='kind', CONF_POLL_INTERVAL='poll_interval',
            DEFAULT_KIND='auto',DEFAULT_POLL_INTERVAL=1.,DeviceState=device,async_get_clientsession=lambda h:None,Platform=NS(BUTTON='button')))
        self.entry=NS(entry_id='entry1',title='Panel',data={'host':'192.0.2.1','device_id':'keep-me'},options={},
            async_on_unload=Mock(),add_update_listener=Mock())

    async def test_add_and_unload_without_restart(self):
        await self.code['async_setup_entry'](self.hass,self.entry)
        device=self.registry['devices']['keep-me']
        device.start_polling.assert_called_once()
        self.assertTrue(await self.code['async_unload_entry'](self.hass,self.entry))
        device.stop_polling.assert_awaited_once()
        self.assertEqual(self.registry,{'devices':{},'entries':{}})

    async def test_address_change_keeps_identity(self):
        self.entry.options={'host':'198.51.100.9'}
        await self.code['async_setup_entry'](self.hass,self.entry)
        self.assertEqual(self.registry['devices']['keep-me'].host,'198.51.100.9')

    async def test_failed_unload_keeps_polling(self):
        await self.code['async_setup_entry'](self.hass,self.entry)
        self.hass.config_entries.async_unload_platforms.return_value=False
        self.assertFalse(await self.code['async_unload_entry'](self.hass,self.entry))
        self.registry['devices']['keep-me'].stop_polling.assert_not_awaited()

    async def test_setup_failure_cleans_registry(self):
        self.hass.config_entries.async_forward_entry_setups.side_effect=RuntimeError('failed platform')
        with self.assertRaises(RuntimeError): await self.code['async_setup_entry'](self.hass,self.entry)
        self.assertEqual(self.registry,{'devices':{},'entries':{}})

    async def test_reload_only_affected_entry(self):
        await self.code['_async_update_entry'](self.hass,self.entry)
        self.hass.config_entries.async_reload.assert_awaited_once_with('entry1')


class FlowBase:
    def __init_subclass__(cls, **kwargs): pass
    async def async_set_unique_id(self, value): self.unique=value
    def _abort_if_unique_id_configured(self):
        if self.unique in self.existing: raise RuntimeError('already_configured')
    def async_create_entry(self,**kw):return kw
    def async_abort(self,**kw):return kw


class ImportTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.code=load_code('config_flow.py',{'duplicate_host','NablaConfigFlow','NablaOptionsFlow'},dict(
            config_entries=NS(ConfigFlow=FlowBase,OptionsFlow=FlowBase),callback=lambda f:f,DOMAIN='nabla_control',
            normalize_host=identity.normalize_host,legacy_id=identity.legacy_id,uuid4=uuid4))
        self.flow=self.code['NablaConfigFlow']();self.flow.existing=[]
        self.entries=[];self.flow.hass=NS(config_entries=NS(async_entries=lambda domain:self.entries))

    async def test_offline_import_preserves_id(self):
        result=await self.flow.async_step_import({'host':'192.0.2.7'})
        self.assertEqual(result['data']['device_id'],'192_0_2_7')

    async def test_reimport_does_not_revert_options(self):
        self.flow.existing=['192_0_2_7']
        with self.assertRaisesRegex(RuntimeError,'already_configured'):
            await self.flow.async_step_import({'host':'192.0.2.7'})

    async def test_duplicate_uses_updated_endpoint(self):
        self.entries.append(NS(entry_id='old',data={'host':'192.0.2.7'},options={'host':'198.51.100.9'}))
        result=await self.flow.async_step_import({'host':'198.51.100.9'})
        self.assertEqual(result,{'reason':'already_configured'})

if __name__ == '__main__': unittest.main()
