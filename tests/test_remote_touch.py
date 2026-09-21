"""Remote tap validation and retry policy with mocked transport."""
import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock
import aiohttp
from test_dynamic_devices import load_code, identity

class TouchTests(IsolatedAsyncioTestCase):
    def setUp(self):
        ns=load_code('__init__.py',{'DeviceState'},dict(aiohttp=aiohttp,asyncio=asyncio,
            DEFAULT_KIND='auto',KIND_WEB='web',http_host=identity.http_host))
        self.session=Mock()
        self.device=ns['DeviceState']('192.0.2.1','Panel',1,self.session)
        self.device.available=True;self.device.kind='mirror';self.device.token='test'
        self.device.capabilities={'width':480,'height':320,'touch':True,'input':False}
        self.device.fetch_token=AsyncMock(return_value=True)
    def responses(self,*statuses):
        class Response:
            def __init__(self,status):self.status=status
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
        self.session.post.side_effect=[Response(s) for s in statuses]
    async def test_success_on_touch_only_device(self):
        self.responses(200)
        self.assertTrue(await self.device.send_touch(479,319))
        self.assertEqual(self.session.post.call_args.kwargs['data'],{'x':'479','y':'319'})
    async def test_reject_outside_coordinates_and_booleans(self):
        for x,y in [(-1,0),(480,0),(0,320),(True,0),(1.2,0)]:
            self.assertFalse(await self.device.send_touch(x,y))
        self.session.post.assert_not_called()
    async def test_no_touch_capability_no_request(self):
        self.device.capabilities.pop('touch')
        self.assertFalse(await self.device.send_touch(0,0));self.session.post.assert_not_called()
    async def test_only_unauthorized_is_retried(self):
        self.responses(401,200)
        self.assertTrue(await self.device.send_touch(0,0));self.device.fetch_token.assert_awaited_once()
        self.responses(409)
        self.assertFalse(await self.device.send_touch(0,0))
    async def test_timeout_not_retried(self):
        self.session.post.side_effect=asyncio.TimeoutError()
        self.assertFalse(await self.device.send_touch(0,0));self.session.post.assert_called_once()
