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

from __future__ import annotations

import asyncio
from typing import Optional, Type

import aiohttp

from .models import ExtractorResult


class BaseExtractor:
    def __init__(self, *, loop: asyncio.AbstractEventLoop = None):
        self.session: aiohttp.ClientSession = None
        self.loop = loop or asyncio.get_event_loop()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def create(self):
        self.session = aiohttp.ClientSession(loop=self.loop)

    @classmethod
    async def process(cls: Type[BaseExtractor], *args, **kwargs) -> Optional[ExtractorResult]:
        loop = asyncio.get_event_loop()
        instance = cls(loop=loop)
        await instance.create()
        await instance.close()
        return None
