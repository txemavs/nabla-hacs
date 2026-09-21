"""Cache behavior with real JPEGs, plus HA adapter lifecycle at mocked boundary."""
import asyncio
import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock
from PIL import Image
from test_dynamic_devices import load_code
import test_dynamic_devices as device_tests

ROOT = Path(__file__).resolve().parents[1]/'custom_components/nabla_control'
spec=importlib.util.spec_from_file_location('nabla_camera_test',ROOT/'camera_cache.py')
cache=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=cache
spec.loader.exec_module(cache)


def jpeg():
    out=BytesIO()
    Image.new('RGB',(1920,1080),'red').save(out,'JPEG')
    return out.getvalue()


class RenderTests(TestCase):
    def test_sizes_aspect_ratio_and_padding(self):
        result=cache.render(jpeg())
        with Image.open(BytesIO(result['view'])) as image:
            self.assertEqual(image.size,(480,270))
            self.assertFalse(image.info.get('progressive',False))
        with Image.open(BytesIO(result['icon'])) as image:
            self.assertEqual(image.size,(64,64))
            self.assertLess(sum(image.getpixel((32,0))),20)
            self.assertGreater(image.getpixel((32,32))[0],200)

    def test_invalid_and_oversized_source(self):
        for source in (b'not an image',b'x'*(cache.MAX_SOURCE_BYTES+1)):
            with self.assertRaises(Exception):cache.render(source)


class CacheTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now=100.
        self.fetch=AsyncMock(return_value=jpeg())
        self.execute=AsyncMock(side_effect=lambda f,*args:f(*args))
        self.cache=cache.CameraCache(self.fetch,self.execute,asyncio.Semaphore(2),clock=lambda:self.now)

    async def asyncTearDown(self):await self.cache.close()

    async def test_23_readers_share_one_capture_and_render(self):
        self.fetch.assert_not_awaited()
        frames=await asyncio.gather(*(self.cache.get() for _ in range(23)))
        self.fetch.assert_awaited_once();self.execute.assert_awaited_once()
        self.assertTrue(all(frame is frames[0] for frame in frames))
        self.assertEqual(set(frames[0].images),{'icon','view'})
        self.assertIs(await self.cache.get(),frames[0])
        self.fetch.assert_awaited_once()

    async def test_stale_reader_returns_while_refreshing(self):
        old=await self.cache.get();self.now+=2
        gate=asyncio.Event()
        async def delayed():await gate.wait();return jpeg()
        self.fetch.side_effect=delayed
        self.assertIs(await self.cache.get(),old)
        pending=self.cache.task
        self.assertIs(await self.cache.get(),old)
        self.assertIs(self.cache.task,pending)
        gate.set();await pending
        self.assertEqual(self.cache.frame.generation,2)

    async def test_failure_is_bounded_and_retries_after_backoff(self):
        self.fetch.side_effect=ValueError('private upstream detail')
        with self.assertRaises(cache.Unavailable):await self.cache.get()
        with self.assertRaises(cache.Unavailable):await self.cache.get()
        self.fetch.assert_awaited_once()
        self.now+=3
        self.fetch.side_effect=None
        self.assertEqual((await self.cache.get()).generation,1)

    async def test_expired_frame_not_returned_on_failure(self):
        await self.cache.get();self.now+=20
        self.fetch.side_effect=ValueError()
        with self.assertRaises(cache.Unavailable):await self.cache.get()

    async def test_cancel_one_reader_does_not_cancel_shared_capture(self):
        gate=asyncio.Event()
        async def delayed():await gate.wait();return jpeg()
        self.fetch.side_effect=delayed
        reader=asyncio.create_task(self.cache.get());await asyncio.sleep(0)
        reader.cancel()
        with self.assertRaises(asyncio.CancelledError):await reader
        self.assertFalse(self.cache.task.cancelled())
        gate.set();self.assertEqual((await self.cache.get()).generation,1)


class CameraEntryTests(IsolatedAsyncioTestCase):
    def setUp(self):
        device_tests.LifecycleTests.setUp(self)
    async def test_camera_entry_does_not_create_device_buttons(self):
        manager=NS(configure=AsyncMock(),close=AsyncMock())
        self.registry['camera_cache']=manager
        self.entry.data={'entry_type':'camera_cache','cameras':['camera.test']}
        await self.code['async_setup_entry'](self.hass,self.entry)
        manager.configure.assert_awaited_once_with(self.entry.data)
        self.hass.config_entries.async_forward_entry_setups.assert_not_awaited()
        self.assertEqual(self.registry['devices'],{})
        await self.code['async_unload_entry'](self.hass,self.entry)
        manager.close.assert_awaited_once()


class RouteTests(IsolatedAsyncioTestCase):
    def setUp(self):
        from aiohttp import web
        self.web=web
        class Base:
            def __init__(self,component):pass
        self.code=load_code('camera.py',{'CachedImageView','LegacyImageView'},dict(
            CameraView=Base,web=web,Unavailable=cache.Unavailable,time=NS(monotonic=lambda:100)))
        self.shared=NS(interval=1,get=AsyncMock(return_value=cache.Frame(
            {'view':b'jpeg','icon':b'small'},{'view':'"v"','icon':'"i"'},100,1)))
        self.caches={'camera.test':self.shared}
        self.view=self.code['CachedImageView'](None,self.caches)
        self.camera=NS(entity_id='camera.test')

    async def test_alias_shares_cache_and_does_not_override_authentication(self):
        legacy=self.code['LegacyImageView'](None,self.caches)
        self.assertIs(legacy.caches,self.view.caches)
        self.assertNotIn('get',self.code['CachedImageView'].__dict__)
        self.assertNotIn('requires_auth',self.code['CachedImageView'].__dict__)
        request=NS(query={'size':'icon'},headers={})
        self.assertEqual((await legacy.handle(request,self.camera)).body,b'small')
        self.assertEqual((await self.view.handle(request,self.camera)).body,b'small')

    async def test_etag_and_invalid_size(self):
        response=await self.view.handle(NS(query={},headers={'If-None-Match':'"v"'}),self.camera)
        self.assertEqual(response.status,304)
        with self.assertRaises(self.web.HTTPBadRequest):
            await self.view.handle(NS(query={'size':'full'},headers={}),self.camera)

    async def test_unconfigured_and_unavailable(self):
        with self.assertRaises(self.web.HTTPNotFound):
            await self.view.handle(NS(query={},headers={}),NS(entity_id='camera.other'))
        self.shared.get.side_effect=cache.Unavailable
        response=await self.view.handle(NS(query={},headers={}),self.camera)
        self.assertEqual(response.status,503)
        self.assertEqual(response.headers['Retry-After'],'2')

class CameraManagerTests(IsolatedAsyncioTestCase):
    async def test_reconfigure_and_close_keep_route_dictionary(self):
        objects=[]
        def create(*args,**kwargs):
            item=NS(close=AsyncMock());objects.append(item);return item
        ns=load_code('camera.py',{'CameraManager'},dict(asyncio=asyncio,
            CAMERA_SCHEMA=lambda options:dict(refresh_interval=1,max_stale=8,quality=70,**options),
            CameraCache=create))
        manager=ns['CameraManager'](NS(async_add_executor_job=Mock()))
        shared=manager.caches
        await manager.configure({'cameras':['camera.one']})
        await manager.configure({'cameras':['camera.two']})
        self.assertIs(manager.caches,shared)
        self.assertEqual(list(shared),['camera.two'])
        objects[0].close.assert_awaited_once()
        await manager.close();self.assertEqual(shared,{})
        objects[1].close.assert_awaited_once()
