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
from typing import TYPE_CHECKING, Dict, List

from internals.db.models import VTHellJobStatus

from ._shared import quick_update_dispatch

if TYPE_CHECKING:
    from internals.db.models import VTHellJob
    from internals.vth import SanicVTHell


logger = logging.getLogger("Internals.FFMPEGDownloader")
__all__ = ("download_via_ffmpeg",)


async def download_via_ffmpeg(
    app: SanicVTHell,
    data: VTHellJob,
    urls: List[str],
    output_file: str,
    http_headers: Dict[str, str] = None,
    extra_args: Dict[str, str] = None,
):
    ffmpeg_args = [app.config.FFMPEG_PATH, "-hide_banner", "-v", "verbose"]
    if isinstance(http_headers, dict):
        ffmpeg_args.extend(
            [
                "-headers",
                "".join(f"{k}: {v}\r\n" for k, v in http_headers.items()),
            ]
        )
    if isinstance(extra_args, dict):
        for key, val in extra_args.items():
            ffmpeg_args.extend([key, val])
    for url in urls:
        ffmpeg_args.extend(["-i", url])
    ffmpeg_args.extend(["-c", "copy", str(output_file), "-y"])
    logger.debug(f"Executing ffmpeg with args: {ffmpeg_args}")
    # Only pipe stderr since stdout is the actual data.
    try:
        ffmpeg_process = await asyncio.create_subprocess_exec(
            *ffmpeg_args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
    except BlockingIOError as ioe:
        logger.error(f"[{data.id}] ffmpeg is blocking, aborting process now", exc_info=ioe)
        return -100, True, "ffmpeg is blocking, aborting process now"

    is_error = False
    already_announced = False
    error_line = None
    while True:
        try:
            async for line in ffmpeg_process.stderr:
                line = line.decode("utf-8").rstrip()
                lower_line = line.lower()
                if "press [q] to stop" in lower_line or ("press" in lower_line and "stop" in lower_line):
                    if not already_announced:
                        already_announced = True
                        await quick_update_dispatch(
                            data,
                            app,
                            VTHellJobStatus.downloading,
                            True,
                            {"resolution": data.resolution or "Unknown"},
                        )
                elif "io error" in lower_line:
                    logger.error(f"[{data.id}] ffmpeg: IO error, cancelling...")
                    is_error = True
                    error_line = line
                    break
                logger.debug(f"[{data.id}] ffmpeg: {line}")
        except ValueError:
            logger.debug(f"[{data.id}] ffmpeg: buffer exceeded, silently ignoring...")
            continue
        else:
            break

    await ffmpeg_process.wait()
    ret_code = ffmpeg_process.returncode
    return ret_code, is_error, error_line
