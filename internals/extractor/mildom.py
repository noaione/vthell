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
from typing import List, Optional, Type

import yt_dlp

from internals.utils import find_cookies_file

from .base import BaseExtractor
from .errors import ExtractorError
from .models import ExtractorResult, ExtractorURLResult

logger = logging.getLogger("Internals.Extractor.Mildom")
__all__ = ("MildomExtractor",)


def select_actual_format(formats: List[dict]):
    video_audio_all = [f for f in formats if f["vcodec"] != "none" and f["acodec"] != "none"]

    video_audio_all.sort(key=lambda f: f["height"], reverse=True)
    return video_audio_all[0]


class MildomExtractor(BaseExtractor):
    def __init__(self, *, loop: asyncio.AbstractEventLoop = None):
        super().__init__(loop=loop)
        self.ydl: yt_dlp.YoutubeDL = None

    async def create(self):
        cookie_file = await find_cookies_file()

        ydl_opts = {
            "live_from_start": True,
            "quiet": True,
        }
        if cookie_file is not None:
            ydl_opts["cookiefile"] = str(cookie_file)

        ydl = await self.loop.run_in_executor(None, yt_dlp.YoutubeDL, ydl_opts)
        logger.debug(f"YoutubeDL (Mildom) options: {ydl_opts}")
        self.ydl = ydl

    @classmethod
    async def process(
        cls: Type[MildomExtractor],
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
            raise ExtractorError(f"Video is geo restricted: {video_url}", "mildom", exc)
        except yt_dlp.utils.ExtractorError as exc:
            await ydl.close()
            logger.error(f"Failed to extract info: {video_url}", exc_info=exc)
            raise ExtractorError(f"Failed to extract info from url {video_url}", "mildom", exc)
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
            raise ExtractorError(error_msg, "mildom", original)

        await ydl.close()
        sanitized = ydl.ydl.sanitize_info(info)
        formats_request = sanitized.get("formats", [])
        if not formats_request:
            logger.error(f"No valid formats found for {video_url}")
            raise ExtractorError(f"No valid formats found for {video_url}", "youtube-dl", None)

        selected_format = select_actual_format(formats_request)
        height = selected_format["height"]
        single_extract = ExtractorURLResult(selected_format["url"], f"{height}p")
        return ExtractorResult([single_extract], "mildom", http_headers={})
