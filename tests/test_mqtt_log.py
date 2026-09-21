# Test memory limits and transactional MQTT subscription lifecycle without a broker.
import ast
import asyncio
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from types import SimpleNamespace as NS, ModuleType
import unittest
from unittest.mock import AsyncMock, Mock, patch

p=Path(__file__).resolve().parents[1]/'custom_components/nabla_control/mqtt_log.py'
tree=ast.parse(p.read_text());tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
ns=dict(asyncio=asyncio,deque=deque,datetime=datetime,timezone=timezone,time=time,callback=lambda f:f,Store=lambda *a:None)
exec(compile(tree,str(p),'exec'),ns)
Buffer=ns['MessageBuffer'];validate=ns['validate_settings'];Monitor=ns['MqttLog']

class BufferTests(unittest.TestCase):
    def test_disabled_by_default(self):self.assertFalse(validate({})['enabled'])
    def test_filters(self):
        self.assertEqual(validate({'enabled':True,'topics':['nabla/+/state/#','nabla/+/state/#']})['topics'],['nabla/+/state/#'])
        for topic in ['nabla/#/x','ab+','x\x00']:
            with self.assertRaises(ValueError):validate({'topics':[topic]})
        with self.assertRaises(ValueError):validate({'enabled':True})
        with self.assertRaises(ValueError):validate({'limit':1001})
    def test_bounded_payload_and_history(self):
        b=Buffer(2)
        for n in range(3):b.append(NS(topic='test',payload=b'x'*3000,retain=True,qos=1))
        self.assertEqual(len(b.rows),2)
        self.assertEqual(len(b.rows[-1]['payload']),2048)
        self.assertTrue(b.rows[-1]['truncated'])
        self.assertTrue(b.rows[-1]['retain'])
    def test_binary_payload(self):
        b=Buffer();b.append(NS(topic='test',payload=b'\xff',retain=False,qos=0))
        self.assertEqual(b.rows[0]['payload'],'\ufffd')
    def test_flood_and_clear(self):
        b=Buffer()
        with patch.object(time,'monotonic',return_value=42):
            for n in range(120):b.append(NS(topic='test',payload=b'a',retain=False,qos=0))
        self.assertEqual(len(b.rows),100);self.assertEqual(b.dropped,20)
        b.clear();self.assertFalse(b.rows);self.assertEqual(b.dropped,0)

class SubscriptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.m=Monitor(None);self.m.store=NS(async_save=AsyncMock(),async_load=AsyncMock(return_value=None))
        self.remove=Mock();self.mqtt=NS(async_wait_for_mqtt_client=AsyncMock(return_value=True),async_subscribe=AsyncMock(return_value=self.remove))
        component=ModuleType('homeassistant.components');component.mqtt=self.mqtt
        self.patch=patch.dict(sys.modules,{'homeassistant':ModuleType('homeassistant'),'homeassistant.components':component})
        self.patch.start();self.addCleanup(self.patch.stop)
    async def test_default_restore_no_subscription(self):
        await self.m.restore();self.mqtt.async_subscribe.assert_not_awaited()
    async def test_enable_and_disable(self):
        await self.m.configure({'enabled':True,'topics':['nabla/#']})
        self.assertTrue(self.m.snapshot()['active'])
        await self.m.configure({'enabled':False})
        self.remove.assert_called_once();self.assertFalse(self.m.snapshot()['active'])
    async def test_partial_failure_preserves_previous(self):
        await self.m.configure({'enabled':True,'topics':['old/#']})
        pending_remove=Mock()
        self.mqtt.async_subscribe.side_effect=[pending_remove,RuntimeError('broker')]
        with self.assertRaises(RuntimeError):await self.m.configure({'enabled':True,'topics':['new/a','new/b']})
        pending_remove.assert_called_once();self.remove.assert_not_called()
        self.assertEqual(self.m.settings['topics'],['old/#'])
    async def test_save_failure_cleans_new_subscription(self):
        self.m.store.async_save.side_effect=OSError('disk')
        with self.assertRaises(RuntimeError):await self.m.configure({'enabled':True,'topics':['new/#']})
        self.remove.assert_called_once();self.assertFalse(self.m.settings['enabled'])
    async def test_missing_broker_does_not_enable(self):
        self.mqtt.async_wait_for_mqtt_client.return_value=False
        with self.assertRaises(RuntimeError):await self.m.configure({'enabled':True,'topics':['nabla/#']})
        self.assertFalse(self.m.snapshot()['active'])
    async def test_stop_unsubscribes(self):
        await self.m.configure({'enabled':True,'topics':['nabla/#']});self.m.stop()
        self.remove.assert_called_once();self.assertFalse(self.m.buffer.rows)

if __name__=='__main__':unittest.main()

class AuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_cannot_read_or_modify(self):
        path=p.with_name('websocket.py')
        module=ast.parse(path.read_text())
        handler=next(n for n in module.body if getattr(n,'name',None)=='websocket_mqtt_log')
        handler.decorator_list=[]
        scope={'DOMAIN':'nabla_control'}
        exec(compile(ast.Module(body=[handler],type_ignores=[]),str(path),'exec'),scope)
        connection=NS(require_admin=Mock(side_effect=PermissionError('admin required')))
        for operation in ['get','configure','clear']:
            with self.assertRaises(PermissionError):
                await scope['websocket_mqtt_log'](None,connection,{'operation':operation})
