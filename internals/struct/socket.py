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

import functools
from typing import TYPE_CHECKING, Any, Optional, Type

if TYPE_CHECKING:
    from ..vth import SanicVTHell

__all__ = ("InternalSocketHandler",)


class InternalSocketHandler:
    event_name: str = ""
    namespace: Optional[str] = None

    @staticmethod
    async def handle(sid: str, data: Any, app: SanicVTHell):
        return None

    @classmethod
    def attach(cls: Type[InternalSocketHandler], app: SanicVTHell):
        if not cls.event_name:
            raise ValueError("event_name must be set")
        bounded_handle = functools.partial(cls.handle, app=app)
        app.sio.on(cls.event_name, bounded_handle, namespace=cls.namespace)
