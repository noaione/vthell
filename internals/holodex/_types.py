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

from typing import List, Literal, Optional, TypedDict

HolodexVideoStatus = Literal["new", "upcoming", "live", "past", "missing"]
HolodexChannelType = Literal["vtuber", "subber"]


class HolodexChannelPartial(TypedDict):
    id: str
    name: str
    org: str
    type: HolodexChannelType
    photo: str
    english_name: str


class HolodexChannel(HolodexChannelPartial):
    suborg: Optional[str]
    banner: str
    twitter: Optional[str]
    video_count: Optional[str]
    subscriber_count: Optional[str]
    view_count: Optional[str]
    clip_count: Optional[int]
    lang: Optional[str]
    published_at: str
    inactive: bool
    description: str


class _HolodexVideoOptional(TypedDict, total=False):
    start_scheduled: str
    start_actual: str
    end_actual: str
    live_viewers: int


class HolodexVideo(_HolodexVideoOptional):
    id: str
    title: str
    topic_id: str
    published_at: str
    type: Literal["stream", "clip"]
    available_at: str
    duration: int
    status: HolodexVideoStatus
    channel: HolodexChannelPartial


class HolodexPaginatedVideo(TypedDict):
    total: int
    items: List[HolodexVideo]
