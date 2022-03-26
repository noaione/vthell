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
from typing import Optional, Type

import yt_dlp

from internals.utils import find_cookies_file

from .base import BaseExtractor
from .errors import ExtractorError
from .models import ExtractorResult, ExtractorURLResult

logger = logging.getLogger("Internals.Extractor.Twitcasting")
__all__ = ("TwitcastingExtractor",)


def ydl_format_selector(ctx):
    """Select the best video and the best audio that won't result in an mkv.
    This is just an example and does not handle all cases"""

    # formats are already sorted worst to best
    formats = ctx.get("formats")[::-1]

    # acodec='none' means there is no audio
    best_video = next(
        f for f in formats if f["vcodec"] != "none" and f["acodec"] == "none" and f["ext"] == "mp4"
    )

    # find compatible audio extension
    audio_ext = {"mp4": "m4a", "webm": "webm"}[best_video["ext"]]
    # vcodec='none' means there is no video
    best_audio = next(
        f for f in formats if (f["acodec"] != "none" and f["vcodec"] == "none" and f["ext"] == audio_ext)
    )

    yield {
        # These are the minimum required fields for a merged format
        "format_id": f'{best_video["format_id"]}+{best_audio["format_id"]}',
        "ext": best_video["ext"],
        "requested_formats": [best_video, best_audio],
        # Must be + separated list of protocols
        "protocol": f'{best_video["protocol"]}+{best_audio["protocol"]}',
    }


class TwitcastingExtractor(BaseExtractor):
    def __init__(self, *, loop: asyncio.AbstractEventLoop = None):
        super().__init__(loop=loop)
        self.ydl: yt_dlp.YoutubeDL = None

    async def create(self):
        cookie_file = await find_cookies_file()

        ydl_opts = {
            "format": ydl_format_selector,
            "live_from_start": True,
            "quiet": True,
        }
        if cookie_file is not None:
            ydl_opts["cookiefile"] = str(cookie_file)

        ydl = await self.loop.run_in_executor(None, yt_dlp.YoutubeDL, ydl_opts)
        logger.debug(f"YoutubeDL (Twitcasting) options: {ydl_opts}")
        self.ydl = ydl

    @classmethod
    async def process(
        cls: Type[TwitcastingExtractor],
        video_url: str,
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> Optional[ExtractorResult]:
        ydl = cls(loop=loop)
        await ydl.create()

        try:
            info = await ydl.loop.run_in_executor(
                None, ydl.ydl.extract_info, video_url, False, None, None, False
            )
        except yt_dlp.utils.GeoRestrictedError as exc:
            await ydl.close()
            logger.error(f"Video is geo restricted: {video_url}")
            raise ExtractorError(f"Video is geo restricted: {video_url}", "twitcasting", exc)
        except yt_dlp.utils.ExtractorError as exc:
            await ydl.close()
            logger.error(f"Failed to extract info: {video_url}", exc_info=exc)
            raise ExtractorError(f"Failed to extract info from url {video_url}", "twitcasting", exc)
        except yt_dlp.utils.DownloadError as exc:
            await ydl.close()
            logger.error(f"Failed to download video: {video_url}", exc_info=exc)
            try:
                original = exc.exc_info[1]
            except IndexError:
                original = exc
            error_msg = f"Failed to extract video from url {video_url}"
            if isinstance(original, yt_dlp.utils.ExtractorError):
                reason = original.msg.lower()
                if "captcha" in reason:
                    error_msg += ": Captcha required"
                elif "private video" in reason:
                    error_msg += ": Video is private"
                elif "no video formats" in reason:
                    error_msg += ": Members-only video"
            raise ExtractorError(error_msg, "twitcasting", original)

        await ydl.close()
        sanitized = ydl.ydl.sanitize_info(info)
        formats_request = sanitized.get("requested_formats", [])
        try:
            video_format = formats_request[0]
        except IndexError:
            formats_request = sanitized.get("formats", [])[::-1]
            try:
                video_format = formats_request[0]
            except IndexError as exc:
                logger.error(f"No valid formats found for {video_url}")
                raise ExtractorError(f"No valid formats found for {video_url}", "youtube-dl", exc)

        single_extract = ExtractorURLResult(video_format["url"], "XXXp")

        return ExtractorResult([single_extract], "twitcasting", http_headers={})
