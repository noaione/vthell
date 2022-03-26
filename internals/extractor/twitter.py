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
import re
from typing import Optional, Type

import orjson

from .base import BaseExtractor
from .errors import ExtractorError
from .models import ExtractorResult, ExtractorURLResult

__all__ = ("TwitterSpaceExtractor",)
logger = logging.getLogger("Internals.Extractor.Twitter")


def backoff_retries(retry_number: int, multiplier: int):
    base_number = 2
    if retry_number == 0:
        return base_number
    return base_number * multiplier ** retry_number


class TwitterSpaceExtractor(BaseExtractor):
    async def _get_token(self):
        async with self.session.get("https://twitter.com") as resp:
            data = await resp.text()
            guest_token = re.search(r"(?<=gt=)\d{19}", data).group(0)
            return guest_token

    async def _persistent_get_token(self):
        max_retries = 3
        for i in range(max_retries):
            try:
                logger.debug(f"Trying to get token (attempt {i + 1}/{max_retries})")
                return await self._get_token()
            except Exception:
                retry_in = backoff_retries(i + 1, 2)
                logger.debug(f"Failed to gain token, retrying in {retry_in} seconds")
                await asyncio.sleep(retry_in)
        raise ExtractorError("Failed to get twitter token", "twitter")

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def create(self, token: Optional[str] = None):
        await super().create()
        if token is None:
            token = await self._persistent_get_token()
        self.session.headers.update(
            {
                "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",  # noqa
                "x-guest-token": token,
            }
        )

    async def get_space_metadata(self, space_id: str):
        params = {
            "variables": orjson.dumps(
                {
                    "id": space_id,
                    "isMetatagsQuery": "false",
                    "withSuperFollowsUserFields": "false",
                    "withBirdwatchPivots": "false",
                    "withDownvotePerspective": "false",
                    "withReactionsMetadata": "false",
                    "withReactionsPerspective": "false",
                    "withSuperFollowsTweetFields": "false",
                    "withReplays": "false",
                    "withScheduledSpaces": "false",
                }
            ).decode("utf-8")
        }

        async with self.session.get(
            "https://twitter.com/i/api/graphql/Uv5R_-Chxbn1FEkyUkSW2w/AudioSpaceById", params=params
        ) as resp:
            json_data = await resp.json()
        return json_data["data"]["audioSpace"]

    async def get_space_stream_status(self, media_key: str):
        async with self.session.get(
            f"https://twitter.com/i/api/1.1/live_video_stream/status/{media_key}"
        ) as resp:
            text = await resp.text()
            return orjson.loads(text)

    @classmethod
    async def process(
        cls: Type[TwitterSpaceExtractor],
        space_id: str,
        token: Optional[str] = None,
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> Optional[ExtractorResult]:
        space = cls(loop=loop)
        if space.session is None:
            await space.create(token=token)
        metadata = await space.get_space_metadata(space_id)
        try:
            space_status = await space.get_space_stream_status(metadata["metadata"]["media_key"])
        except Exception:
            space_status = None
        await space.close()

        if space_status is None:
            return space_status

        return ExtractorResult(
            urls=[ExtractorURLResult(url=space_status["source"]["location"])],
            extractor="twitter",
            http_headers={
                "x-guest-token": space.session.headers.get("x-guest-token"),
                "Authorization": space.session.headers.get("Authorization")
                or space.session.headers.get("authorization"),
            },
        )
