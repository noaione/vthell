"""
MIT License

Copyright (c) 2020-present noaione

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, List, Optional

if TYPE_CHECKING:
    from streamlink.stream.hls import HLSStream, HLSStreamReader

__all__ = ("ExtractorURLResult", "ExtractorResult", "StreamlinkExtractorResult")


@dataclass
class ExtractorURLResult:
    url: str
    resolution: Optional[str] = None


@dataclass
class ExtractorResult:
    urls: List[ExtractorURLResult]
    extractor: str
    http_headers: Dict[str, str] = field(default_factory=dict)
    chat: Optional[Callable[..., Coroutine[Any, Any, None]]] = None


@dataclass
class StreamlinkExtractorResult:
    stream: HLSStream
    extractor: str
    resolution: str
    worker: Optional[HLSStreamReader] = None
    loop: Optional[asyncio.AbstractEventLoop] = None

    def __post_init__(self):
        self.loop = self.loop or asyncio.get_event_loop()

    async def open(self):
        if self.worker is None:
            self.worker = await self.loop.run_in_executor(None, self.stream.open)

    async def read(self, bita: int = 4096):
        if self.worker is None:
            await self.open()

        data = await self.loop.run_in_executor(
            None,
            self.worker.read,
            bita,
        )
        return data

    async def close(self):
        if self.worker is not None:
            await self.loop.run_in_executor(None, self.worker.close)
            self.worker = None
