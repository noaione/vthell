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
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Type
from zipfile import ZipFile

import aiofiles
import aiofiles.os
import aiofiles.ospath
import aiohttp
import pendulum

from internals.constants import archive_gh, hash_gh
from internals.struct import InternalTaskBase

if TYPE_CHECKING:
    from internals.vth import SanicVTHell


logger = logging.getLogger("Tasks.DatasetUpdater")
BASE_PATH = Path(__file__).absolute().parent.parent.parent
DATASET_PATH = BASE_PATH / "dataset"

__all__ = ("DatasetUpdaterTasks",)


class DatasetUpdaterTasks(InternalTaskBase):
    @staticmethod
    async def dl_and_extract():
        as_bytes_io = BytesIO()
        async with aiohttp.ClientSession() as session:
            async with session.get(archive_gh) as resp:
                assert resp.status == 200
                raw_bytes = await resp.read()
                as_bytes_io.write(raw_bytes)

        as_bytes_io.seek(0)

        with ZipFile(as_bytes_io) as zip:
            for file in zip.filelist:
                fp_path = DATASET_PATH / file
                async with aiofiles.open(str(fp_path), "wb") as fp:
                    await fp.write(zip.read(file))

    @staticmethod
    async def executor(time: int, task_name: str) -> None:
        logger.info("Running dataset updater task %s (%d)", task_name, time)

        async with aiohttp.ClientSession() as session:
            async with session.get(hash_gh) as resp:
                current_hash = await resp.text()

        current_hash = current_hash.split("\n")[0].strip()
        logger.info("Latest hash are %s", current_hash)

        dataset_hash = DATASET_PATH / "currentversion"
        if not await aiofiles.ospath.isfile(dataset_hash):
            logger.info("No dataset hash file found, downloading...")
            await DatasetUpdaterTasks.dl_and_extract()
            async with aiofiles.open(str(dataset_hash), "w") as fp:
                fp.write(current_hash)
            logger.info("Downloaded and saved hash")
            return

        async with aiofiles.open(str(dataset_hash), "r") as fp:
            old_hash = (await fp.readlines())[0].strip()

        logger.info("Old hash are %s", old_hash)
        if old_hash == current_hash:
            logger.info("Dataset is up to date")
            return

        logger.info("Dataset is outdated, downloading...")
        await DatasetUpdaterTasks.dl_and_extract()
        async with aiofiles.open(str(dataset_hash), "w") as fp:
            fp.write(current_hash)
        logger.info("Downloaded and saved hash")

    @classmethod
    async def main_loop(cls: Type[DatasetUpdaterTasks], app: SanicVTHell):
        await app.wait_until_ready()
        try:
            while True:
                ctime = pendulum.now("UTC").int_timestamp
                task_name = f"DatasetUpdaterTask-{ctime}"
                task = app.loop.create_task(cls.executor(ctime, task_name), name=task_name)
                task.add_done_callback(cls.executor_done)
                cls._tasks[task_name] = task
                await cls.executor(ctime, f"DatasetUpdater-{ctime}")
                await asyncio.sleep(1 * 60 * 60)
        except asyncio.CancelledError:
            logger.warning("Got cancel signal, cleaning up all running tasks")
            for name, task in cls._tasks.items():
                if name.startswith("DatasetUpdaterTask"):
                    task.cancel()
