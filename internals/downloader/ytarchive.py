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
from os import getenv
from typing import TYPE_CHECKING

from internals.db import VTHellJobStatus
from internals.utils import find_cookies_file, map_to_boolean

from ._shared import quick_update_dispatch

if TYPE_CHECKING:
    from internals.db import VTHellJob
    from internals.vth import SanicVTHell


logger = logging.getLogger("Internals.YTArchiveDownloader")
__all__ = ("download_via_ytarchive",)


async def download_via_ytarchive(
    data: VTHellJob,
    app: SanicVTHell,
    output_file: str,
):
    cookies_file = await find_cookies_file()
    notify_chat_dl = map_to_boolean(getenv("VTHELL_CHAT_DOWNLOADER", "false"))

    # Spawn ytarchive
    ytarchive_args = [
        app.config.YTARCHIVE_PATH,
        "-4",
        "--wait",
        "-r",
        "30",
        "-v",
        "--newline",
        "-o",
        str(output_file),
    ]
    if cookies_file is not None:
        ytarchive_args.extend(["-c", str(cookies_file)])
    ytarchive_args.extend([f"https://www.youtube.com/watch?v={data.id}", "best"])
    logger.debug(f"[{data.id}] Executing ytarchive with args: {ytarchive_args}")

    try:
        ytarchive_process = await asyncio.create_subprocess_exec(
            *ytarchive_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except BlockingIOError as ioe:
        logger.error(f"[{data.id}] ytarchive is blocking, aborting process now", exc_info=ioe)
        return -100, True, "ytarchive is blocking, aborting process now"
    is_error = False
    already_announced = False
    error_line = None
    while True:
        try:
            async for line in ytarchive_process.stdout:
                line = line.decode("utf-8").rstrip()
                lower_line = line.lower()
                if "selected quality" in lower_line:
                    actual_quality = line.split(": ")[1].split()[0]
                    data.resolution = actual_quality
                    await data.save()
                    logger.info(f"Selected quality: {actual_quality}")
                elif "error" in lower_line:
                    is_error = True
                    error_line = line
                    logger.error(f"[{data.id}] {line}")
                    break
                elif "unable to retrieve" in lower_line:
                    is_error = True
                    logger.error(f"[{data.id}] {line}")
                    error_line = line
                    break
                elif "could not find" in lower_line:
                    is_error = True
                    logger.error(f"[{data.id}] {line}")
                    error_line = line
                    break
                elif "unable to download" in lower_line:
                    is_error = True
                    logger.error(f"[{data.id}] {line}")
                    error_line = line
                    break
                elif "starting download" in lower_line and not already_announced:
                    already_announced = True
                    await quick_update_dispatch(
                        data,
                        app,
                        VTHellJobStatus.downloading,
                        True,
                        {"resolution": data.resolution or "Unknown"},
                    )
                    if notify_chat_dl:
                        await app.dispatch("internals.chat.manager", context={"app": app, "video": data})
                elif "livestream" in lower_line and "process" in lower_line:
                    is_error = True
                    logger.error(f"[{data.id}] {line}")
                    error_line = line
                if "total downloaded" in lower_line:
                    logger.debug(f"[{data.id}] {line}")
                    if not already_announced:
                        logger.info(f"[{data.id}] Download started for both video and audio")
                        already_announced = True
                        await quick_update_dispatch(
                            data,
                            app,
                            VTHellJobStatus.downloading,
                            True,
                            {"resolution": data.resolution or "Unknown"},
                        )
                        if notify_chat_dl:
                            await app.dispatch("internals.chat.manager", context={"app": app, "video": data})
                else:
                    logger.debug(f"[{data.id}] {line}")
        except ValueError:
            logger.debug(f"[{data.id}] ytarchive buffer exceeded, silently ignoring...")
            continue
        else:
            break

    await ytarchive_process.wait()
    ret_code = ytarchive_process.returncode
    if error_line is None and (is_error or ret_code != 0):
        error_line = await ytarchive_process.stderr.read()
        error_line = error_line.decode("utf-8").rstrip()
    return ret_code, is_error, error_line
