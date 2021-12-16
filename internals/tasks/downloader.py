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
from pathlib import Path
from typing import TYPE_CHECKING, Type

import aiofiles.os
import pendulum

from internals.db import models
from internals.struct import InternalTaskBase
from internals.utils import build_rclone_path, find_cookies_file, map_to_boolean

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

logger = logging.getLogger("Tasks.Downloader")
STREAMDUMP_PATH = Path(__file__).absolute().parent.parent.parent / "streamdump"
STREAMDUMP_PATH.mkdir(exist_ok=True, parents=True)

__all__ = ("DownloaderTasks",)


class DownloaderTasks(InternalTaskBase):
    @staticmethod
    async def mux_files(data: models.VTHellJob, app: SanicVTHell):
        # Spawn mkvmerge
        temp_output = STREAMDUMP_PATH / f"{data.filename} [temp].mp4"
        if not temp_output.exists():
            logger.warning(f"[{data.id}] downloaded file not found, skipping.")
            return True
        mux_output = STREAMDUMP_PATH / f"{data.filename} [{data.resolution} AAC].mkv"
        mkvmerge_args = [app.config.MKVMERGE_PATH, "-o", str(mux_output), str(temp_output)]

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
            data.last_status = models.VTHellJobStatus.muxing
            data.error = f"mkvmerge exited with code {ret_code}:\n{stderr}"
            await app.sio.emit(
                "job_update", {"id": data.id, "status": "ERROR", "error": "MKV_MUX_FAIL"}, namespace="/vthell"
            )
            return True
        return False

    @staticmethod
    async def upload_files(data: models.VTHellJob, app: SanicVTHell):
        mux_output = STREAMDUMP_PATH / f"{data.filename} [{data.resolution} AAC].mkv"
        if not mux_output.exists():
            logger.warning(f"[{data.id}] muxed file not found, skipping.")
            return True

        base_folder = "Stream Archive"
        if data.member_only:
            base_folder = "Member-Only Stream Archive"
        joined_target = []
        joined_target = app.create_rclone_path(data.channel_id, "youtube")

        target_folder = build_rclone_path(app.config.RCLONE_DRIVE_TARGET, base_folder, *joined_target)
        rclone_args = [app.config.RCLONE_PATH, "-v", "-P", "copy", str(mux_output), target_folder]
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
            data.status = models.VTHellJobStatus.error
            data.last_status = models.VTHellJobStatus.uploading
            data.error = f"rclone exited with code {ret_code}:\n{error_line}"
            await data.save()
            await app.sio.emit(
                "job_update",
                {"id": data.id, "status": "ERROR", "error": "RCLONE_UPLOAD_FAIL"},
                namespace="/vthell",
            )
            return True
        return False

    @staticmethod
    async def cleanup_files(data: models.VTHellJob, app: SanicVTHell):
        mux_output = STREAMDUMP_PATH / f"{data.filename} [{data.resolution} AAC].mkv"
        temp_output = STREAMDUMP_PATH / f"{data.filename} [temp].mp4"
        try:
            logger.info(f"[{data.id}] Trying to delete temporary mp4 files...")
            await aiofiles.os.remove(str(temp_output))
        except Exception:
            logger.exception(f"[{data.id}] Failed to delete temporary mp4 files, silently skipping")

        if app.config.RCLONE_DISABLE:
            logger.info(f"[{data.id}] Rclone is disabled, skipping muxed mkv deletion...")
            return
        try:
            logger.info(f"[{data.id}] Trying to delete muxed mkv files...")
            await aiofiles.os.remove(str(mux_output))
        except Exception:
            logger.exception(f"[{data.id}] Failed to delete muxed mkv files, silently skipping")

    @staticmethod
    async def propagate_error(data: models.VTHellJob, app: SanicVTHell):
        logger.info(f"[{data.id}] Trying to process error job.")
        if data.last_status == models.VTHellJobStatus.muxing:
            logger.info(f"[{data.id}][m] Last status was mux job, trying to redo from mux point.")
            is_error = await DownloaderTasks.mux_files(data, app)
            if is_error:
                logger.error(f"[{data.id}][m] Failed to redo mux job, aborting.")
                return
            logger.info(f"[{data.id}][m] Mux job redone, continuing with upload files...")
            if not app.config.RCLONE_DISABLE:
                await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.uploading, True)
                is_error = await DownloaderTasks.upload_files(data, app)
                if is_error:
                    logger.error(f"[{data.id}][m] Failed to do upload job, aborting.")
                    return
                logger.info(f"[{data.id}][m] Upload job done, cleaning files...")
            else:
                logger.info(f"[{data.id}][m] Upload step skipped since Rclone is disabled...")
            await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.cleaning, True)
            await DownloaderTasks.cleanup_files(data, app)
            logger.info(f"[{data.id}] Cleanup job done, marking job as finished!")
            data.status = models.VTHellJobStatus.done
            data.error = None
            data.last_status = None
            await data.save()
        elif data.last_status == models.VTHellJobStatus.uploading:
            logger.info(f"[{data.id}] Last status was upload job, trying to redo from upload point.")
            if not app.config.RCLONE_DISABLE:
                await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.uploading, True)
                is_error = await DownloaderTasks.upload_files(data, app)
                if is_error:
                    logger.error(f"[{data.id}][u] Failed to redo upload job, aborting.")
                    return
                logger.info(f"[{data.id}][u] Upload job redone, cleaning files...")
            else:
                logger.info(f"[{data.id}][u] Upload restep skipped since Rclone is disabled...")
            await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.cleaning, True)
            await DownloaderTasks.cleanup_files(data, app)
            logger.info(f"[{data.id}][u] Cleanup job done, marking job as finished!")
            data.status = models.VTHellJobStatus.done
            data.error = None
            data.last_status = None
            await data.save()
        elif data.last_status == models.VTHellJobStatus.cleaning:
            logger.info(f"[{data.id}][c] Last status was cleanup job, trying to redo from cleanup point.")
            await DownloaderTasks.cleanup_files(data, app)
            logger.info(f"[{data.id}][c] Cleanup job redone, marking job as finished!")
            data.status = models.VTHellJobStatus.done
            data.error = None
            data.last_status = None
            await data.save()

    @staticmethod
    async def update_state(
        data: models.VTHellJob, app: SanicVTHell, status: models.VTHellJobStatus, notify: bool = False
    ):
        data.status = status
        data.error = None
        data.last_status = None
        await data.save()
        await app.sio.emit("job_update", {"id": data.id, "status": status.value}, namespace="/vthell")
        if notify:
            await app.dispatch(
                "internals.notifier.discord",
                context={"app": app, "data": data, "emit_type": "update"},
            )

    @staticmethod
    async def executor(data: models.VTHellJob, time: int, task_name: str, app: SanicVTHell):
        logger.info(f"Executing job {data.id} (task {task_name})")
        grace_period = data.start_time - app.config.VTHELL_GRACE_PERIOD
        if time < grace_period:
            logger.info(f"Job {data.id} skipped since it's still far away from grace period")
            return

        if True:
            print(f"CALLED BY {task_name}")
            return

        if data.status != models.VTHellJobStatus.waiting:
            if data.status == models.VTHellJobStatus.error:
                await DownloaderTasks.propagate_error(data, app)
            else:
                logger.info(f"Job {data.id} skipped since it's being processed")
            return

        logger.info(f"Trying to start job {data.id}")
        await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.preparing)
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
        is_error = False
        already_announced = False
        should_cancel = False
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
                        await DownloaderTasks.update_state(
                            data, app, models.VTHellJobStatus.downloading, True
                        )
                    elif "livestream" in lower_line and "process" in lower_line:
                        is_error = True
                        logger.error(f"[{data.id}] {line}")
                        error_line = line
                        should_cancel = True
                    if "total downloaded" in lower_line:
                        logger.debug(f"[{data.id}] {line}")
                        if not already_announced:
                            logger.info(f"[{data.id}] Download started for both video and audio")
                            already_announced = True
                            await DownloaderTasks.update_state(
                                data, app, models.VTHellJobStatus.downloading, True
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
            data.last_status = models.VTHellJobStatus.downloading
            data.status = models.VTHellJobStatus.error
            if should_cancel:
                data.status = models.VTHellJobStatus.done
            data.error = f"ytarchive exited with code {ret_code} ({error_line})"
            await data.save()
            await app.sio.emit(
                "job_update", {"id": data.id, "status": "ERROR", "error": data.error}, namespace="/vthell"
            )
            return

        await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.muxing, True)
        logger.info(f"Job {data.id} finished downloading, muxing into mkv files...")
        is_error = await DownloaderTasks.mux_files(data, app)
        if is_error:
            return

        if not app.config.RCLONE_DISABLE:
            await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.uploading, True)
            logger.info(f"Job {data.id} finished muxing, uploading to drive target...")
            is_error = await DownloaderTasks.upload_files(data, app)
            if is_error:
                return
            logger.info(f"Job {data.id} finished uploading, deleting temp files...")
        else:
            logger.info(f"Job {data.id} finished muxing, skipping upload since rclone is disabled...")

        data.status = models.VTHellJobStatus.cleaning
        data.error = None
        data.last_status = None
        await data.save()
        await app.dispatch(
            "internals.notifier.discord",
            context={"app": app, "data": data, "emit_type": "update"},
        )
        await app.sio.emit("job_update", {"id": data.id, "status": "DONE"}, namespace="/vthell")

        await DownloaderTasks.cleanup_files(data, app)
        logger.info(f"Job {data.id} finished cleaning up, setting job as finished...")
        data.status = models.VTHellJobStatus.done
        data.error = None
        data.last_status = None
        await data.save()

    @staticmethod
    async def get_scheduled_job():
        try:
            all_jobs = await models.VTHellJob.all()
            all_jobs = list(filter(lambda job: job.status != models.VTHellJobStatus.done, all_jobs))
        except Exception as e:
            logger.error(f"Failed to get scheduled jobs: {e}", exc_info=e)
            return []
        return all_jobs

    @classmethod
    async def main_loop(cls: Type[DownloaderTasks], app: SanicVTHell):
        loop = app.loop
        config = app.config
        await app.wait_until_ready()
        try:
            while True:
                if map_to_boolean(getenv("SKIP_MAIN_TASK", "0")):
                    logger.info("Skipping main task loop")
                    return
                ctime = pendulum.now("UTC").int_timestamp
                logger.info(f"Checking for scheduled jobs at {ctime}")
                scheduled_jobs = await cls.get_scheduled_job()
                for job in scheduled_jobs:
                    task_name = f"downloader-{job.id}-{ctime}"
                    try:
                        task = loop.create_task(cls.executor(job, ctime, task_name, app), name=task_name)
                        task.add_done_callback(cls.executor_done)
                        cls._tasks[task_name] = task
                    except Exception as e:
                        logger.error(f"Failed to create task {task_name}: {e}", exc_info=e)
                if not scheduled_jobs:
                    logger.info("No scheduled jobs found")
                await asyncio.sleep(config.VTHELL_LOOP_DOWNLOADER)
        except asyncio.CancelledError:
            logger.warning("Got cancel signal, cleaning up all running tasks")
            for name, task in cls._tasks.items():
                if name.startswith("downloader-"):
                    task.cancel()
