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
from typing import List, Literal, Optional

__all__ = ("VTHellRecords",)


@dataclass
class VTHellRecords:
    id: str
    name: str
    type: Literal["folder", "file"]
    toggled: Optional[bool] = None
    children: Optional[List[VTHellRecords]] = None
    size: Optional[int] = None
    mimetype: Optional[str] = None
    modtime: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    def to_json(self) -> dict:
        base = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
        }
        for child in self.children:
            base["children"] = []
            base["children"].append(child.to_json())
        if self.size is not None:
            base["size"] = self.size
        if self.children is not None:
            base["children"] = self.children
        if self.toggled is not None:
            base["toggled"] = self.toggled
        if self.mimetype is not None:
            base["mimetype"] = self.mimetype
        if self.modtime is not None:
            base["modtime"] = self.modtime
        return base
