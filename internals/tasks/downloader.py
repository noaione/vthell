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
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Type

import aiofiles.os
import pendulum

from internals.db import models
from internals.struct import InternalTaskBase
from internals.utils import build_rclone_path, find_cookies_file

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

logger = logging.getLogger("Tasks.Downloader")
STREAMDUMP_PATH = Path(__file__).absolute().parent.parent.parent / "streamdump"
STREAMDUMP_PATH.mkdir(exist_ok=True, parents=True)

__all__ = ("DownloaderTasks",)


class DownloaderTasks(InternalTaskBase):
    _tasks: Dict[str, asyncio.Task] = {}

    @staticmethod
    async def executor(data: models.VTHellJob, time: int, task_name: str, app: SanicVTHell):
        logger.info(f"Executing job {data.id} (task {task_name})")
        grace_period = data.start_time - app.config.VTHELL_GRACE_PERIOD
        if time < grace_period:
            logger.info(f"Job {data.id} skipped since it's still far away from grace period")
            return

        if data.status != models.VTHellJobStatus.waiting:
            logger.info(f"Job {data.id} skipped since it's being processed")
            return

        data.status = models.VTHellJobStatus.preparing
        await data.save()

        dataset_info, vt_info = app.find_id_on_dataset(data.channel_id, "youtube")

        logger.info(f"Trying to start job {data.id}")
        await app.sio.emit("job_update", {"id": data.id, "status": data.status.value}, namespace="/vthell")
        temp_output_file = STREAMDUMP_PATH / f"{data.filename} [temp]"
        cookies_file = await find_cookies_file()

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
            str(temp_output_file),
        ]
        if cookies_file is not None:
            ytarchive_args.extend(["-c", cookies_file])
        ytarchive_args.append(f"https://youtube.com/watch?v={data.id}")
        ytarchive_args.append("best")
        logger.debug(f"[{data.id}] Starting ytarchive with args: {ytarchive_args}")
        ytarchive_process = await asyncio.create_subprocess_exec(
            *ytarchive_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        quality_res = None
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
                        quality_res = actual_quality
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
                        data.status = models.VTHellJobStatus.downloading
                        await data.save()
                        await app.sio.emit(
                            "job_update", {"id": data.id, "status": data.status.value}, namespace="/vthell"
                        )
                    if "total downloaded" in lower_line:
                        logger.debug(f"[{data.id}] {line}")
                        if not already_announced:
                            already_announced = True
                            data.status = models.VTHellJobStatus.downloading
                            await data.save()
                            await app.dispatch(
                                "internals.notifier.discord",
                                context={"app": app, "data": data, "emit_type": "update"},
                            )
                            await app.sio.emit(
                                "job_update",
                                {"id": data.id, "status": data.status.value},
                                namespace="/vthell",
                            )
                    else:
                        logger.info(f"[{data.id}] {line}")
            except ValueError:
                logger.debug(f"[{data.id}] ytarchive buffer exceeded, silently ignoring...")
                continue
            else:
                break

        await ytarchive_process.wait()
        ret_code = ytarchive_process.returncode
        if is_error or ret_code != 0:
            logger.error(f"[{data.id}] ytarchive exited with code {ret_code}")
            data.status = models.VTHellJobStatus.error
            data.error = f"ytarchive exited with code {ret_code} ({error_line})"
            await data.save()
            await app.sio.emit("job_failed", {"id": data.id}, namespace="/vthell")
            return

        data.status = models.VTHellJobStatus.muxing
        await data.save()
        logger.info(f"Job {data.id} finished downloading, muxing into mkv files...")
        await app.sio.emit("job_update", {"id": data.id, "status": data.status.value}, namespace="/vthell")

        # Spawn mkvmerge
        mux_output = STREAMDUMP_PATH / f"{data.filename} [{quality_res} AAC].mkv"
        mkvmerge_args = [app.config.MKVMERGE_PATH, "-o", str(mux_output), str(temp_output_file) + ".mp4"]

        logger.debug(f"[{data.id}] Starting mkvmerge with args: {mkvmerge_args}")
        mkvmerge_process = await asyncio.create_subprocess_exec(
            *mkvmerge_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await mkvmerge_process.wait()
        ret_code = mkvmerge_process.returncode
        if ret_code != 0:
            logger.error(
                f"[{data.id}] mkvmerge exited with code {ret_code}, aborting uploading please do manual upload later!"
            )
            stderr = await mkvmerge_process.stderr.read()
            stdout = await mkvmerge_process.stdout.read()
            if not stderr:
                stderr = stdout
            stderr = stderr.decode("utf-8").rstrip()
            data.status = models.VTHellJobStatus.error
            data.error = f"mkvmerge exited with code {ret_code}:\n{stderr}"
            await app.sio.emit(
                "job_update", {"id": data.id, "status": "DONE", "error": "MKV_MUX_FAIL"}, namespace="/vthell"
            )
            return

        logger.info(f"Job {data.id} finished muxing, uploading to drive target...")
        data.status = models.VTHellJobStatus.uploading
        await data.save()
        await app.dispatch(
            "internals.notifier.discord",
            context={"app": app, "data": data, "emit_type": "update"},
        )
        await app.sio.emit("job_update", {"id": data.id, "status": data.status.value}, namespace="/vthell")
        joined_target = []
        if dataset_info is None:
            joined_target.extend(["Unknown", mux_output])
        else:
            main_target = dataset_info.upload_base.replace("\\", "/").split("/")
            joined_target.extend(main_target)
            joined_target.append(vt_info.name)
            joined_target.append(mux_output)
        base_folder = "Stream Archive"
        if data.member_only:
            base_folder = "Member-Only Stream Archive"
        target_folder = build_rclone_path(app.config.RCLONE_DRIVE_TARGET, base_folder, *joined_target)
        rclone_args = [app.config.RCLONE_PATH, "-v", "-P", "copy", str(mux_output), target_folder]
        logger.debug(f"[{data.id}] Starting rclone with args: {rclone_args}")
        rclone_process = await asyncio.create_subprocess_exec(
            *rclone_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await rclone_process.wait()
        ret_code = rclone_process.returncode
        if ret_code != 0:
            logger.error(
                f"[{data.id}] rclone exited with code {ret_code}, aborting uploading please do manual upload later!"
            )
            stderr = await mkvmerge_process.stderr.read()
            stdout = await mkvmerge_process.stdout.read()
            if not stderr:
                stderr = stdout
            stderr = stderr.decode("utf-8").rstrip()
            data.status = models.VTHellJobStatus.error
            data.error = f"rclone exited with code {ret_code}:\n{stderr}"
            await data.save()
            await app.sio.emit(
                "job_update",
                {"id": data.id, "status": "DONE", "error": "RCLONE_UPLOAD_FAIL"},
                namespace="/vthell",
            )
            return

        logger.info(f"Job {data.id} finished uploading, deleting temp files...")
        data.status = models.VTHellJobStatus.cleaning
        await data.save()
        await app.dispatch(
            "internals.notifier.discord",
            context={"app": app, "data": data, "emit_type": "update"},
        )
        await app.sio.emit("job_update", {"id": data.id, "status": "DONE"}, namespace="/vthell")

        try:
            await aiofiles.os.remove(str(temp_output_file) + ".mp4")
        except Exception:
            pass
        try:
            await aiofiles.os.remove(mux_output)
        except Exception:
            pass

        logger.info(f"Job {data.id} finished cleaning up, setting job as finished...")
        data.status = models.VTHellJobStatus.done
        await data.save()

    @classmethod
    def executor_done(cls: Type[DownloaderTasks], task: asyncio.Task):
        task_name = task.get_name()
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"Task {task_name} failed with exception: {exception}", exc_info=exception)
        except asyncio.exceptions.InvalidStateError:
            pass
        logger.info(f"Task {task_name} finished")
        cls._tasks.pop(task_name, None)

    @staticmethod
    async def get_scheduled_job():
        all_jobs = await models.VTHellJob.all()
        all_jobs = list(filter(lambda job: job.status == models.VTHellJobStatus.waiting, all_jobs))
        return all_jobs

    @classmethod
    async def main_loop(cls: Type[DownloaderTasks], app: SanicVTHell):
        loop = app.loop
        config = app.config
        await app.wait_until_ready()
        try:
            while True:
                ctime = pendulum.now("UTC").int_timestamp
                logger.info(f"Checking for scheduled jobs at {ctime}")
                all_tasks = []
                for job in await cls.get_scheduled_job():
                    task_name = f"downloader-{job.id}-{ctime}"
                    task = loop.create_task(cls.executor(job, ctime, task_name, app), name=task_name)
                    task.add_done_callback(cls.executor_done)
                    all_tasks.append(task)
                if not all_tasks:
                    logger.info("No scheduled jobs found")
                await asyncio.gather(*all_tasks)
                await asyncio.sleep(config.VTHELL_LOOP_DOWNLOADER)
        except asyncio.CancelledError:
            logger.warning("Got cancel signal, cleaning up all running tasks")
            for task in cls._tasks.values():
                task.cancel()
