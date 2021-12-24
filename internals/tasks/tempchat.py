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
from typing import TYPE_CHECKING, List, Optional, Type

import aiofiles
import orjson
import pendulum

from internals.chat.parser import complex_walk
from internals.db import VTHellJob, VTHellJobChatTemporary, VTHellJobStatus
from internals.struct import InternalTaskBase

if TYPE_CHECKING:
    from internals.vth import SanicVTHell


logger = logging.getLogger("Tasks.TemporaryChat")
__all__ = ("TemporaryChatTasks",)


async def backtrack_read_json(file_path: str, max_size: int = -5000) -> Optional[dict]:
    print("Opening file:", file_path)
    fp = await aiofiles.open(file_path, "rb")
    await fp.seek(0, os.SEEK_END)

    current = -1
    read_json: Optional[List[dict]] = None
    # Little by litte read the data until it reach the maximum backtracking
    # This function is much efficient than reading a 100mb file directly.
    while current > max_size:
        await fp.seek(current, os.SEEK_END)
        data = await fp.read()
        await fp.seek(0, os.SEEK_END)
        decoded = data.decode("utf-8")
        current -= 1

        # We dont want to add our opening bracket
        # before there is a curly bracket since it will stop at:
        # [], before it until parse anything meaningful
        if decoded.endswith("}\n]") or decoded.endswith("}]"):
            decoded = "[\n" + decoded

        try:
            read_json = orjson.loads(decoded)
            break
        except orjson.JSONDecodeError:
            pass

    await fp.close()
    if isinstance(read_json, list) and len(read_json) > 0:
        return read_json[-1]
    return None


class TemporaryChatTasks(InternalTaskBase):
    @staticmethod
    async def executor(chat_job: VTHellJobChatTemporary, task_name: str, app: SanicVTHell) -> None:
        video_data = await VTHellJob.get_or_none(id=chat_job.id)
        if video_data is None:
            logger.warning(f"{task_name}: Job not found, dispatching upload task for <{chat_job.id}>...")
            await app.dispatch("internals.chat.uploader", context={"job": chat_job, "app": app})
            return

        if video_data.status not in [
            VTHellJobStatus.waiting,
            VTHellJobStatus.preparing,
            VTHellJobStatus.downloading,
            VTHellJobStatus.error,
        ]:
            if chat_job.is_done:
                logger.info(f"{task_name}: Job <{chat_job.id}> is done, dispatching upload...")
                await app.dispatch("internals.chat.uploader", context={"job": chat_job, "app": app})
            else:
                logger.warning(f"{task_name}: Job <{chat_job.id}> is finished, dispatching with force rewrite...")
                await app.dispatch(
                    "internals.chat.manager", context={"app": app, "video": video_data, "force": True}
                )
            return

        # Video exist, time to read it temporarily to check the last timestamp of the message
        # Loading this to memory might be a really bad idea lmao.
        last_content = await backtrack_read_json(video_data.filename)
        last_timestamp = None
        if isinstance(last_content, dict):
            last_timestamp = complex_walk(last_content, "timestamp")
        logger.info(f"Dispatching downloader for <{video_data.id}> with last timestamp at {last_timestamp}")
        await app.dispatch(
            "internals.chat.manager",
            context={
                "app": app,
                "video": video_data,
                "last_timestamp": last_timestamp,
            },
        )

    @classmethod
    async def main_loop(cls: Type[TemporaryChatTasks], app: SanicVTHell):
        await app.wait_until_ready()
        if not app.first_process:
            logger.warning("TempChat is not running in the first process, skipping it")
            return
        try:
            ctime = pendulum.now("UTC").int_timestamp
            temporary_chats = await VTHellJobChatTemporary.all()
            for chat_job in temporary_chats:
                task_name = f"TempChat-Dispatcher-{chat_job.id}_{ctime}"
                task = app.loop.create_task(cls.executor(chat_job, task_name, app))
                task.add_done_callback(cls.executor_done)
                cls._tasks[task_name] = task
        except asyncio.CancelledError:
            logger.warning("TempChat is cancelled, cleaning up running tasks...")
            for name, task in cls._tasks.items():
                if name.startswith("TempChat-Dispatcher"):
                    task.cancel()
