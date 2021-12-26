from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, List, Optional, Type

import aiohttp

from internals.utils import complex_walk, map_to_boolean
from .models import ihaAPIVideo
from ._types import ihaAPIVTuberVideo

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
        query_send = {"query": QUERY_OBJECT, "variables": {"platforms": platforms, "cursor": None}}

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
