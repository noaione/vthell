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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from sanic.server.websockets.connection import WebSocketConnection

__all__ = ("WebSocketPacket", "WebSocketMessage")


@dataclass
class WebSocketPacket:
    event: str
    data: Optional[Any] = None
    to: Optional[str] = None

    @classmethod
    def from_ws(cls, data: dict) -> WebSocketPacket:
        if not isinstance(data, dict):
            raise TypeError("data must be a dict")
        event = data.get("event")
        content = data.get("data")
        if event is None:
            raise ValueError("event is required")
        target = data.get("to")
        return cls(event, content, target)

    def to_ws(self) -> dict:
        return {
            "event": self.event,
            "data": self.data,
        }

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "data": self.data,
            "to": self.to,
        }


@dataclass
class WebSocketMessage:
    sid: str
    packet: WebSocketPacket
    ws: Optional[WebSocketConnection]
