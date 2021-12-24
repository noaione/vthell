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
from typing import TYPE_CHECKING, Any, Dict

from internals.chat.client import ChatDownloader
from internals.chat.utils import float_or_none
from internals.chat.writer import JSONWriter
from internals.db.models import VTHellJobChatTemporary
from internals.struct import InternalSignalHandler

if TYPE_CHECKING:
    from internals.db import VTHellJob
    from internals.vth import SanicVTHell

logger = logging.getLogger("Internals.ChatManager")

__all__ = ("ChatDownloaderManager",)


class ChatManager:
    _actives: Dict[str, ChatDownloader] = {}

    @property
    def actives(self):
        return self._actives

    @property
    def keys(self):
        return list(self._actives.keys())


class ChatDownloaderManager(InternalSignalHandler):
    signal_name = "internals.chat.manager"

    @staticmethod
    async def main_loop(**context: Dict[str, Any]):
        app: SanicVTHell = context.get("app")
        if app is None:
            logger.error("app context is missing!")
            return
        video: VTHellJob = context.get("video")
        if video is None:
            logger.error("video context is missing!")
            return
        if video.id in ChatManager._actives:
            logger.error("Chat %s is already being downloaded!", video.id)
            return
        logger.info("Starting chat downloader for %s", video.id)
        last_timestamp = context.get("last_timestamp")
        if last_timestamp is not None and not isinstance(last_timestamp, (int, float)):
            last_timestamp = float_or_none(last_timestamp)
        chat_downloader = ChatDownloader(video.id)
        filename = video.filename + ".chat.json"
        jwriter = JSONWriter(filename, False)
        ChatManager._actives[video.id] = chat_downloader
        is_async_cancel = False
        chat_job = await VTHellJobChatTemporary.get_or_create(
            id=video.id, filename=filename, channel_id=video.channel_id, member_only=video.member_only
        )
        try:
            await chat_downloader.start(jwriter, last_timestamp)
        except asyncio.CancelledError:
            logger.info("Chat downloader for %s was cancelled, flushing...", video.id)
            is_async_cancel = True
        ChatManager._actives.pop(video.id, None)
        await jwriter.close()
        if not is_async_cancel:
            logger.info("Chat downloader for %s finished, sending upload signal", video.id)
            await app.dispatch("internals.chat.uploader", context={"job": chat_job, "app": app})
        else:
            logger.info("Chat downloader for %s was cancelled", video.id)
