from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Type

import aiofiles
import streamlink

from internals.utils import find_cookies_file, parse_cookie_to_morsel

from .base import BaseExtractor
from .models import StreamlinkExtractorResult

if TYPE_CHECKING:
    from streamlink.plugins.twitch import TwitchHLSStream

logger = logging.getLogger("Internals.Extractor.Twitch")
__all__ = ("TwitchExtractor",)


async def read_and_parse_cookie(cookie_file: Optional[Path]):
    if cookie_file is None:
        return None

    try:
        async with aiofiles.open(cookie_file, "r") as f:
            cookie_data = await f.read()
    except OSError as exc:
        logger.error(f"Could not read cookie file {cookie_file}", exc_info=exc)
        return None

    try:
        cookie_jar = parse_cookie_to_morsel(cookie_data)
    except ValueError:
        logger.error(f"Failed to parse cookie file {cookie_file}")
        return None

    base_cookies = []
    for cookie in cookie_jar.values():
        base_cookies.append(cookie.OutputString())

    return ";".join(base_cookies)


class TwitchExtractor(BaseExtractor):
    def __init__(self, *, loop: asyncio.AbstractEventLoop = None):
        super().__init__(loop=loop)
        self.sl: streamlink.Streamlink = None

    async def create(self):
        cookie_file = await find_cookies_file()
        cookie_headers = await read_and_parse_cookie(cookie_file)
        sl = streamlink.Streamlink()
        if cookie_headers is not None:
            sl.set_option("http-cookie", cookie_headers)

        sl.set_plugin_option("twitch", "disable_reruns", True)
        sl.set_plugin_option("twitch", "disable_hosting", True)
        sl.set_plugin_option("twitch", "disable-ads", True)
        sl.set_plugin_option("twitch", "low-latency", True)
        sl.set_option("hls-live-edge", 2)
        sl.set_option("stream-timeout", 30)

        self.sl = sl

    @classmethod
    async def process(
        cls: Type[TwitchExtractor], url: str, *, loop: asyncio.AbstractEventLoop = None
    ) -> Optional[StreamlinkExtractorResult]:
        if "twitch.tv" not in url:
            return None
        loop = loop or asyncio.get_event_loop()
        logger.info(f"[twitch] Processing: {url}")
        sl = cls(loop=loop)
        await sl.create()
        streams = await loop.run_in_executor(None, sl.sl.streams, url)
        await sl.close()
        if not streams:
            logger.error(f"[twitch] No streams found for {url}")
            return None
        streams.pop("best", None)
        streams.pop("audio_only", None)
        streams.pop("worst", None)
        try:
            best_stream_key = list(streams.keys())[-1]
        except IndexError:
            logger.error(f"[twitch] No streams found for {url}")
            return None

        logger.info(f"[twitch] Found stream {best_stream_key}")

        best_stream: Optional[TwitchHLSStream] = streams.get(best_stream_key)
        if best_stream is None:
            logger.error(f"[twitch] No streams found for {url}")
            return None

        return StreamlinkExtractorResult(
            stream=best_stream, extractor="twitch", resolution=best_stream_key, loop=loop
        )
