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
from typing import TYPE_CHECKING, List, Optional, Type, Union

import aiohttp
import pendulum

from ._types import HolodexPaginatedVideo
from ._types import HolodexVideo as HolodexVideoPayload
from ._types import HolodexVideoStatus
from .models import HolodexVideo

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

__all__ = ("HolodexAPI",)

logger = logging.getLogger("Internals.Holodex")


class HolodexAPI:
    BASE = "https://holodex.net/api/v2/"

    def __init__(self, api_key: Optional[str] = None, *, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.api_key = api_key
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
        if self.api_key:
            self.client.headers.update({"X-APIKEY": self.api_key})
        self.__ready = True

    @staticmethod
    def _convert_date_to_unix(date_time: Optional[str]) -> Optional[int]:
        if date_time is None:
            return None
        dt = pendulum.parse(date_time, tz="UTC")
        return dt.int_timestamp

    async def get_channel_videos(self, channel_id: str):
        params = {
            "limit": 50,
            "include": "live_info",
        }
        request_path = f"{self.BASE}channels/{channel_id}/videos"
        async with self.client.get(request_path, params=params) as response:
            if response.status != 200:
                return []
            response_json: List[HolodexVideoPayload] = await response.json()

        coerced_data: List[HolodexVideo] = []
        for video in response_json:
            video_type = video.get("type")
            if video_type != "stream":
                continue
            start_time = self._convert_date_to_unix(video.get("start_actual"))
            if start_time is None:
                start_time = self._convert_date_to_unix(video.get("start_scheduled"))
            channel_id = video.get("channel_id") or video.get("channel", {}).get("id")
            if channel_id is None:
                continue

            org_group = video.get("channel", {}).get("org")
            video_url = f"https://youtube.com/watch?v={video['id']}"
            is_member = "member" in video.get("topic_id", "").lower()
            coerced_data.append(
                HolodexVideo(
                    video["id"],
                    video["title"],
                    start_time,
                    channel_id,
                    org_group,
                    video["status"],
                    video_url,
                    is_member,
                )
            )

        return coerced_data

    async def close(self):
        if self.client and not self.client.closed:
            await self.client.close()

    @staticmethod
    def to_int(number: Union[str, int]):
        if isinstance(number, str):
            return int(number)
        return number

    async def _get_videos_paginated(self, status: HolodexVideoStatus, endpoint: str):
        sort_by = "available_at"
        if status == "upcoming":
            sort_by = "start_scheduled"
        elif status == "live":
            sort_by = "start_actual"
        limitation = 50
        params = {
            "type": "stream",
            "include": "live_info",
            "sort": sort_by,
            "order": "asc",
            "limit": limitation,
            "paginated": "true",
            "max_upcoming_hours": 48,
        }
        if status is not None:
            params["status"] = status
        collected_videos: List[HolodexVideoPayload] = []
        offset = 0
        while True:
            params["offset"] = offset
            async with self.client.get(f"{self.BASE}{endpoint}", params=params) as response:
                if response.status != 200:
                    break
                response_json: List[HolodexPaginatedVideo] = await response.json()

            total_item = self.to_int(response_json.get("total", "0"))
            if total_item < 1:
                break

            collected_videos.extend(response_json["items"])
            offset += limitation + 1
            if len(collected_videos) >= total_item:
                break

        return collected_videos

    async def get_lives(self):
        async with self.client.get(f"{self.BASE}live") as response:
            if response.status != 200:
                logger.error(f"Failed to get live videos: {response.status}")
                return []
            try:
                results: List[HolodexVideoPayload] = await response.json()
            except Exception:
                logger.exception("Failed to parse live videos")
                return []

        coerced_data: List[HolodexVideo] = []
        for video in results:
            video_type = video.get("type")
            if video_type != "stream":
                continue
            start_time = self._convert_date_to_unix(video.get("start_actual"))
            if start_time is None:
                start_time = self._convert_date_to_unix(video.get("start_scheduled"))
            channel_id = video.get("channel_id") or video.get("channel", {}).get("id")
            if channel_id is None:
                continue

            org_group = video.get("channel", {}).get("org")

            video_url = f"https://youtube.com/watch?v={video['id']}"
            is_member = "member" in video.get("topic_id", "").lower()
            coerced_data.append(
                HolodexVideo(
                    video["id"],
                    video["title"],
                    start_time,
                    channel_id,
                    org_group,
                    video["status"],
                    video_url,
                    is_member,
                )
            )

        return coerced_data

    async def get_video(self, video_id: str) -> Optional[HolodexVideo]:
        params = {"id": video_id, "include": "live_info"}

        async with self.client.get(f"{self.BASE}videos", params=params) as resp:
            if resp.status != 200:
                return None
            json_resp: List[HolodexVideoPayload] = await resp.json()

        if len(json_resp) < 1:
            return None

        selected_video = json_resp[0]

        if selected_video is None:
            return None

        video_type = selected_video.get("type")
        if video_type != "stream":
            # Dont archive clipper stuff because why would you do that?
            return None
        stream_status = selected_video.get("status")
        if stream_status is None:
            # Somehow it's missing the status? Remove it.
            return None
        if stream_status == "missing":
            # Stream is private, dont add.
            return None
        start_time = self._convert_date_to_unix(selected_video.get("start_actual"))
        if start_time is None:
            start_time = self._convert_date_to_unix(selected_video.get("start_scheduled"))
        channel_id = selected_video.get("channel_id") or selected_video.get("channel", {}).get("id")
        if channel_id is None:
            return None
        org_group = selected_video.get("channel", {}).get("org")

        video_url = f"https://youtube.com/watch?v={selected_video['id']}"
        is_member = "member" in selected_video.get("topic_id", "").lower()
        return HolodexVideo(
            selected_video["id"],
            selected_video["title"],
            start_time,
            channel_id,
            org_group,
            stream_status,
            video_url,
            is_member,
        )

    @classmethod
    def attach(cls: Type[HolodexAPI], app: SanicVTHell):
        config = app.config.get("HOLODEX_API_KEY")

        async def init_holodex_api(app: SanicVTHell):
            holodex = cls(config, loop=app.loop)
            logger.info("Initializing Holodex API")
            await holodex.create()
            app.holodex = holodex
            app.mark_holodex_ready()
            logger.info("Holodex API initialized")

        app.add_task(init_holodex_api)
