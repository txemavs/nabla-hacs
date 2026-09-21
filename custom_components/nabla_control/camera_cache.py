"""Demand-driven JPEG cache, independent of Home Assistant."""
import asyncio
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import time

from PIL import Image, ImageOps

MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_SOURCE_PIXELS = 16_000_000


def render(source, quality=70):
    """Create baseline JPEG variants from one source, in an executor."""
    if len(source) > MAX_SOURCE_BYTES:
        raise ValueError("Source too large")
    with Image.open(BytesIO(source)) as original:
        if original.width * original.height > MAX_SOURCE_PIXELS:
            raise ValueError("Source dimensions too large")
        image = ImageOps.exif_transpose(original).convert("RGB")
    image.thumbnail((480, 480), Image.Resampling.LANCZOS)
    icon = ImageOps.pad(image, (64, 64), method=Image.Resampling.LANCZOS,
                        color="black", centering=(0.5, 0.5))
    result = {}
    for name, pixels in (("view", image), ("icon", icon)):
        out = BytesIO()
        pixels.save(out, "JPEG", quality=quality, progressive=False, optimize=False)
        data = out.getvalue()
        if len(data) > 128 * 1024:
            raise ValueError("Encoded image too large")
        result[name] = data
    return result


@dataclass(frozen=True)
class Frame:
    images: dict
    etags: dict
    created: float
    generation: int


class Unavailable(Exception):
    """No sufficiently recent frame is available."""


class CameraCache:
    """One in-flight capture and one immutable pair of JPEGs per camera."""

    def __init__(self, fetch, execute, gate, interval=1.0, max_stale=8.0,
                 quality=70, clock=time.monotonic):
        self.fetch, self.execute, self.gate = fetch, execute, gate
        self.interval, self.max_stale, self.quality = interval, max_stale, quality
        self.clock = clock
        self.frame = None
        self.task = None
        self.retry_after = 0.0
        self.generations = 0
        self.failures = 0

    async def _refresh(self):
        try:
            async with self.gate:
                async with asyncio.timeout(10):
                    source = await self.fetch()
                captured = self.clock()
                # Do not cancel the executor on a request timeout: retain the
                # single-flight task until rendering really finishes.
                images = await self.execute(render, source, self.quality)
            self.generations += 1
            self.frame = Frame(images, {
                k: '"' + sha256(v).hexdigest() + '"' for k, v in images.items()
            }, captured, self.generations)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never expose camera URLs/tokens or upstream exception text.
            self.failures += 1
            self.retry_after = self.clock() + max(2.0, self.interval)
        finally:
            self.task = None

    async def get(self):
        now = self.clock()
        if self.frame and now - self.frame.created < self.interval:
            return self.frame
        if self.task is None and now >= self.retry_after:
            self.task = asyncio.create_task(self._refresh())
        # Warm readers never wait for another client's refresh.
        if self.frame and now - self.frame.created <= self.max_stale:
            return self.frame
        if self.task:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=15)
            except TimeoutError:
                raise Unavailable from None
        if self.frame and self.clock() - self.frame.created <= self.max_stale:
            return self.frame
        raise Unavailable

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
