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

from enum import Enum, IntEnum
from typing import Optional, Type

import orjson
from tortoise import fields
from tortoise.models import Model

__all__ = ("VTHellJob", "VTHellAutoType", "VTHellAutoScheduler", "VTHellJobStatus", "VTHellJobChatTemporary")


def orjson_dumps(obj: object) -> bytes:
    return orjson.dumps(
        obj,
        option=orjson.OPT_NON_STR_KEYS | orjson.OPT_PASSTHROUGH_DATACLASS | orjson.OPT_SERIALIZE_DATACLASS,
    ).decode("utf-8")


class VTHellJobStatus(str, Enum):
    # Not downloading
    waiting = "WAITING"
    # Currently being processed
    preparing = "PREPARING"
    # Download has been called
    downloading = "DOWNLOADING"
    # Download complete, now muxing
    muxing = "MUXING"
    # Muxing complete, now uploading
    uploading = "UPLOAD"
    # Upload complete, now cleaning up
    cleaning = "CLEANING"
    # Cleanup complete, now done
    done = "DONE"
    # Error
    error = "ERROR"


class VTHellJob(Model):
    id = fields.CharField(pk=True, unique=True, index=True, max_length=128)
    title = fields.TextField(null=False)
    filename = fields.TextField(null=False)
    resolution = fields.CharField(null=True, max_length=24)
    start_time = fields.BigIntField(null=False)
    channel_id = fields.TextField(null=False)
    member_only = fields.BooleanField(null=False, default=False)
    status = fields.CharEnumField(VTHellJobStatus, null=False, default=VTHellJobStatus.waiting, max_length=24)
    last_status = fields.CharEnumField(VTHellJobStatus, null=True, max_length=24)
    error = fields.TextField(null=True)


class VTHellJobChatTemporary(Model):
    id = fields.CharField(pk=True, unique=True, index=True, max_length=128)
    filename = fields.TextField(null=False)
    channel_id = fields.TextField(null=False)
    member_only = fields.BooleanField(null=False, default=False)


class VTHellAutoType(IntEnum):
    channel = 1
    group = 2
    word = 3
    regex_word = 4

    @classmethod
    def from_name(cls: Type[VTHellAutoType], name: str) -> Optional[VTHellAutoType]:
        return getattr(cls, name, None)


class VTHellAutoScheduler(Model):
    type = fields.IntEnumField(VTHellAutoType)
    data = fields.TextField(null=False)
    # Only included if type is word/regex_word
    # Used to chain with other data types
    chains = fields.JSONField(null=True, encoder=orjson_dumps, decoder=orjson.loads)
    include = fields.BooleanField(null=False, default=True)
