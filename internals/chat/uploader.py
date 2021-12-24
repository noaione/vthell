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
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from internals.db import VTHellJobChatTemporary
from internals.struct import InternalSignalHandler
from internals.utils import build_rclone_path

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

__all__ = ("ChatDownloaderUploaderReceiver",)
logger = logging.getLogger("ChatJob.Uploader")
CHATDUMP_PATH = Path(__file__).absolute().parent.parent.parent / "chatarchive"


async def upload_files(data: VTHellJobChatTemporary, app: SanicVTHell):
    final_output = CHATDUMP_PATH / data.filename
    if not final_output.exists():
        logger.warning(f"[{data.id}] chat dump not found, skipping")
        await data.delete()
        return

    base_folder = "Chat Archive"
    if data.member_only:
        base_folder = "Member-Only Chat Archive"

    joined_target = []
    joined_target = app.create_rclone_path(data.channel_id, "youtube")
    target_folder = build_rclone_path(app.config.RCLONE_DRIVE_TARGET, base_folder, *joined_target)

    rclone_args = [app.config.RCLONE_PATH, "-v", "-P", "copy", str(final_output), target_folder]
    logger.debug(f"[{data.id}] Starting rclone with args: {rclone_args}")
    rclone_process = await asyncio.create_subprocess_exec(
        *rclone_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    error_line = ""
    while True:
        try:
            async for line in rclone_process.stdout:
                line = line.decode("utf-8").rstrip()
                logger.debug(f"[{data.id}] rclone: {line}")
                if "error" in line.lower():
                    error_line = line
                elif "failed to copy" in line.lower():
                    error_line = line
        except Exception:
            logger.debug(f"[{data.id}] rclone buffer exceeded, silently ignoring...")
            continue
        else:
            break

    await rclone_process.wait()
    ret_code = rclone_process.returncode
    if ret_code != 0:
        logger.error(
            f"[{data.id}] rclone exited with code {ret_code}, aborting uploading please do manual upload later!"
        )
        logger.error(error_line)
        return
    await data.delete()

    try:
        await app.loop.run_in_executor(None, os.remove, str(final_output))
    except Exception:
        logger.exception(f"[{data.id}] Failed to remove temporary file")


class ChatDownloaderUploaderReceiver(InternalSignalHandler):
    signal_name = "internals.chat.uploader"

    @staticmethod
    async def main_loop(**context: Dict[str, Any]):
        app: SanicVTHell = context.get("app")
        if app is None:
            logger.error("app context is missing!")
            return
        chat_job: VTHellJobChatTemporary = context.get("job")
        if chat_job is None:
            logger.error("chat job context is missing!")
            return

        try:
            await upload_files(chat_job, app)
        except asyncio.CancelledError:
            logger.debug(f"[{chat_job.id}] Cancelled")
        except Exception as e:
            logger.exception(f"[{chat_job.id}] Failed to upload chat archive", exc_info=e)
