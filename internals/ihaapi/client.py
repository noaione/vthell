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
import logging
from typing import TYPE_CHECKING, List, Optional, Type

import aiohttp

from internals.utils import complex_walk, map_to_boolean

from ._types import ihaAPIVTuberVideo
from .models import ihaAPIVideo

if TYPE_CHECKING:
    from internals.vth import SanicVTHell


DEFAULT_PLATFORMS = ["twitter", "twitcasting"]
logger = logging.getLogger("Internals.ihaAPI")
__all__ = ("ihateanimeAPI",)


QUERY_OBJECT = """
query VTuberLive($cursor:String,$platforms:[PlatformName]) {
    vtuber {
        videos(cursor:$cursor,limit:100,platforms:$platforms,statuses:[live,upcoming]) {
            _total
            items {
                id
                title
                status
                channel_id
                timeData {
                    startTime
                    scheduledStartTime
                    endTime
                }
                platform
                group
                is_premiere
                is_member
            }
            pageInfo {
                hasNextPage
                nextCursor
            }
        }
    }
}

query VTuberVideo($id:String,$platforms:[PlatformName],$statuses:[LiveStatus]) {
    vtuber {
        videos(id:[$id],limit:10,platforms:$platforms,statuses:$statuses) {
            items {
                id
                title
                status
                channel_id
                timeData {
                    startTime
                    scheduledStartTime
                    endTime
                }
                platform
                group
                is_premiere
                is_member
            }
        }
    }
}
"""


class ihateanimeAPI:
    BASE = "https://api.ihateani.me/v2/graphql"

    def __init__(self, *, loop: Optional[asyncio.AbstractEventLoop] = None):
        self._loop = loop or asyncio.get_event_loop()
        self.client: aiohttp.ClientSession = None
        self.__ready: bool = False

    @property
    def ready(self) -> bool:
        return self.__ready

    async def create(self):
        self.client = aiohttp.ClientSession(
            loop=self._loop,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "VTHell/3.0.0 (+https://github.com/noaione/vthell)",
            },
        )
        self.__ready = True

    async def close(self):
        if self.client and not self.client.closed:
            await self.client.close()
        self.client = None
        self.__ready = False

    async def get_lives(self, platforms: List[str] = DEFAULT_PLATFORMS):
        query_send = {
            "query": QUERY_OBJECT,
            "variables": {"platforms": platforms, "cursor": None},
            "operationName": "VTuberLive",
        }

        all_data: List[ihaAPIVTuberVideo] = []
        while True:
            async with self.client.post(self.BASE, json=query_send) as response:
                if response.status != 200:
                    break
                response_json = await response.json()
                vtuber_live = complex_walk(response_json, "data.vtuber.videos")
                if vtuber_live is None:
                    break
                all_data.extend(vtuber_live["items"])
                next_cursor = complex_walk(vtuber_live, "pageInfo.nextCursor")
                if next_cursor is None:
                    break
                query_send["variables"]["cursor"] = next_cursor

        parsed_videos: List[ihaAPIVideo] = []
        for video in all_data:
            start_time = complex_walk(video, "timeData.startTime") or complex_walk(
                video, "timeData.scheduledStartTime"
            )
            iha_video = ihaAPIVideo(
                id=video["id"],
                title=video["title"],
                start_time=start_time,
                channel_id=video["channel_id"],
                status=video["status"],
                platform=video["platform"],
                is_member=map_to_boolean(video["is_member"]),
            )
            parsed_videos.append(iha_video)
        return parsed_videos

    async def get_video(self, video_id: str, platform: str):
        query_send = {
            "query": QUERY_OBJECT,
            "variables": {
                "platforms": [platform],
                "cursor": None,
                "id": video_id,
                "statuses": ["live", "upcoming", "past"],
            },
            "operationName": "VTuberVideo",
        }
        if platform == "twitch":
            query_send["variables"]["statuses"] = ["live", "upcoming"]

        all_data: List[ihaAPIVTuberVideo] = []
        async with self.client.post(self.BASE, json=query_send) as response:
            if response.status != 200:
                return None
            response_json = await response.json()
            vtuber_live = complex_walk(response_json, "data.vtuber.videos")
            if vtuber_live is None:
                return None
            all_data.extend(vtuber_live["items"])

        if len(all_data) < 1:
            return None

        selected_video: ihaAPIVTuberVideo = None
        for video in all_data:
            if video["id"] == video_id:
                selected_video = video
                break

        if selected_video is None:
            return None

        start_time = complex_walk(selected_video, "timeData.startTime") or complex_walk(
            selected_video, "timeData.scheduledStartTime"
        )
        iha_video = ihaAPIVideo(
            id=selected_video["id"],
            title=selected_video["title"],
            start_time=start_time,
            channel_id=selected_video["channel_id"],
            status=selected_video["status"],
            platform=selected_video["platform"],
            is_member=map_to_boolean(selected_video["is_member"]),
        )
        return iha_video

    @classmethod
    def attach(cls: Type[ihateanimeAPI], app: SanicVTHell):
        async def init_ihateanime_api(app: SanicVTHell):
            ihaapi = cls(loop=app.loop)
            logger.info("Initializing ihateanime API")
            await ihaapi.create()
            app.ihaapi = ihaapi
            app.mark_ihaapi_ready()
            logger.info("Initialized ihateanime API")

        app.add_task(init_ihateanime_api)
