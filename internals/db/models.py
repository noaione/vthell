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

from enum import IntEnum

from tortoise import fields
from tortoise.models import Model

__all__ = ("VTHellJob", "VTHellAutoType", "VTHellAutoScheduler")


class VTHellJob(Model):
    id = fields.CharField(pk=True, unique=True, index=True, max_length=128)
    title = fields.TextField(null=False)
    filename = fields.TextField(null=False)
    start_time = fields.BigIntField(null=False)
    channel_id = fields.TextField(null=False)
    member_only = fields.BooleanField(null=False, default=False)
    is_downloading = fields.BooleanField(null=False, default=False)
    is_downloaded = fields.BooleanField(null=False, default=False)


class VTHellAutoType(IntEnum):
    channel = 1
    group = 2
    word = 3
    regex_word = 4


class VTHellAutoScheduler(Model):
    type = fields.IntEnumField(VTHellAutoType)
    data = fields.TextField(null=False)
    enabled = fields.BooleanField(null=False, default=True)
