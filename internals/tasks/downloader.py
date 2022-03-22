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
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

import aiofiles
import aiofiles.os
import pendulum
import yt_dlp

from internals.db import models
from internals.downloader import download_via_ffmpeg, download_via_ytarchive
from internals.extractor import (
    ExtractorError,
    MildomExtractor,
    TwitcastingExtractor,
    TwitchExtractor,
    TwitterSpaceExtractor,
    YouTubeExtractor,
)
from internals.struct import InternalTaskBase
from internals.utils import build_rclone_path, find_cookies_file, map_to_boolean, parse_cookie_to_morsel

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

logger = logging.getLogger("Tasks.Downloader")
STREAMDUMP_PATH = Path(__file__).absolute().parent.parent.parent / "streamdump"
STREAMDUMP_PATH.mkdir(exist_ok=True, parents=True)

__all__ = ("DownloaderTasks",)


def ytarchive_should_cancel(errors: str):
    if not errors:
        return False
    lower_error = errors.lower()
    if "private" in lower_error:
        return True
    if "members only" in lower_error:
        return True
    return False


async def read_and_parse_cookie(cookie_file: Optional[Path]):
    if cookie_file is None:
        return None

    try:
        async with aiofiles.open(cookie_file, "r") as f:
            cookie_data = await f.read()
    except OSError as exc:
        logger.error(f"Could not read cookie file {cookie_file}", exc_info=exc)
        return None

    try:
        cookie_jar = parse_cookie_to_morsel(cookie_data)
    except ValueError:
        logger.error(f"Failed to parse cookie file {cookie_file}")
        return None

    base_cookies = []
    for cookie in cookie_jar.values():
        base_cookies.append(cookie.OutputString())

    return "; ".join(base_cookies)


async def find_temporary_file(data: models.VTHellJob, loop: asyncio.AbstractEventLoop = None):
    loop = loop or asyncio.get_event_loop()
    streamdumps = await loop.run_in_executor(None, STREAMDUMP_PATH.iterdir)
    for path in streamdumps:
        if path.name.startswith(data.filename + " [temp]"):
            return path
    return None


class DownloaderTasks(InternalTaskBase):
    @staticmethod
    async def download_video_with_ytarchive(data: models.VTHellJob, app: SanicVTHell):
        temp_output_file = STREAMDUMP_PATH / f"{data.filename} [temp]"

        # Spawn ytarchive
        ret_code, is_error, error_line = await download_via_ytarchive(data, app, temp_output_file)
        if is_error or ret_code != 0:
            logger.error(f"[{data.id}] ytarchive exited with code {ret_code}")
            data.last_status = models.VTHellJobStatus.downloading
            data.status = models.VTHellJobStatus.error
            data.error = f"ytarchive exited with code {ret_code} ({error_line})"
            should_cancel = ytarchive_should_cancel(error_line)
            emit_data = {"id": data.id, "status": "ERROR", "error": data.error}
            if should_cancel:
                data.status = models.VTHellJobStatus.cancelled
                emit_data["status"] = "CANCELLED"
            await data.save()
            await app.wshandler.emit("job_update", emit_data)
            if app.first_process and app.ipc:
                await app.ipc.emit("ws_job_update", emit_data)
            return True, error_line
        return False, None

    @staticmethod
    async def download_video_with_ytdl(data: models.VTHellJob, app: SanicVTHell):
        if data.platform != "youtube":
            return False
        cookie_file = await find_cookies_file()
        cookie_header = await read_and_parse_cookie(cookie_file)
        try:
            ytdl_result = await YouTubeExtractor.process(
                f"https://youtube.com/watch?v={data.id}", loop=app.loop
            )
        except ExtractorError as exc:
            logger.error(f"[{data.id}] {exc}", exc_info=exc)
            data.last_status = models.VTHellJobStatus.downloading
            message = exc.msg.lower()
            error_msg = f"Unable to extract information with yt-dlp ({exc.msg})"
            emit_data = {
                "id": data.id,
                "status": "ERROR",
                "error": error_msg,
            }
            if "private" in message or "captcha" or "geo restrict":
                data.status = models.VTHellJobStatus.cancelled
                emit_data["status"] = "CANCELLED"
            elif isinstance(exc.exc_info, yt_dlp.utils.ExtractorError):
                cause = exc.exc_info.msg.lower()
                if "members-only" in cause or "member-only" in cause:
                    data.status = models.VTHellJobStatus.cancelled
                    emit_data["status"] = "CANCELLED"
            else:
                data.status = models.VTHellJobStatus.error
            data.error = error_msg
            await data.save()
            await app.wshandler.emit("job_update", emit_data)
            if app.first_process and app.ipc:
                await app.ipc.emit("ws_job_update", emit_data)
            return True

        if ytdl_result is None:
            return True

        temp_file = STREAMDUMP_PATH / f"{data.filename} [temp].ts"
        resolution = ytdl_result.urls[0].resolution or ytdl_result.urls[1].resolution or "Unknown"
        logger.debug(f"[{data.id}] Downloading with resolution {resolution} format")
        data.resolution = resolution
        await data.save()

        http_headers = ytdl_result.http_headers or {}
        if cookie_header is not None:
            http_headers["Cookie"] = cookie_header
        ret_code, is_error, error_line = await download_via_ffmpeg(
            app, data, list(map(lambda x: x.url, ytdl_result.urls)), temp_file, http_headers
        )
        if ret_code != 0 or is_error:
            logger.error(f"[{data.id}] ffmpeg exited with code {ret_code}")
            await DownloaderTasks.make_error(
                data,
                app,
                f"ffmpeg exited with code {ret_code}: {error_line}",
                models.VTHellJobStatus.downloading,
            )
            return True
        return False

    @staticmethod
    async def download_stream_youtube(data: models.VTHellJob, app: SanicVTHell):
        is_error, error_line = await DownloaderTasks.download_video_with_ytarchive(data, app)
        if is_error:
            lower_line = error_line.lower() if isinstance(error_line, str) else None
            if isinstance(lower_line, str) and "livestream" in lower_line and "youtube-dl" in lower_line:
                logger.info(f"[{data.id}] Job download failed with ytarchive, trying with YTDL instead")
                is_error = await DownloaderTasks.download_video_with_ytdl(data, app)
                if is_error:
                    logger.error(f"[{data.id}] Failed to download video with ytdl, aborting.")
                    return True, None
                return False, STREAMDUMP_PATH / f"{data.filename} [temp].ts"
            else:
                logger.error(f"[{data.id}] Failed to download video with ytarchive, aborting.")
                return True, None
        return False, STREAMDUMP_PATH / f"{data.filename} [temp].mp4"

    @staticmethod
    async def download_stream_twitter_spaces(data: models.VTHellJob, app: SanicVTHell):
        if data.platform != "twitter":
            return True, None

        space_id = data.id.replace("twtsp-", "")
        spaces_info = await TwitterSpaceExtractor.process(space_id, loop=app.loop)
        if spaces_info is None:
            return True, None

        temp_output = STREAMDUMP_PATH / f"{data.filename} [temp].m4a"
        ret_code, is_error, error_line = await download_via_ffmpeg(
            app,
            data,
            spaces_info.urls[0].url,
            temp_output,
            spaces_info.http_headers,
            {
                "-metadata": f"title={data.title}",
            },
        )
        if ret_code != 0 or is_error:
            logger.error(f"[{data.id}] ffmpeg exited with code {ret_code}")
            await DownloaderTasks.make_error(
                data,
                app,
                f"ffmpeg exited with code {ret_code}: {error_line}",
                models.VTHellJobStatus.downloading,
            )
            return True, None
        return False, temp_output

    @staticmethod
    async def download_twitcasting_stream(data: models.VTHellJob, app: SanicVTHell):
        if data.platform != "twitcasting":
            return True, None

        cookie_file = await find_cookies_file()
        cookie_header = await read_and_parse_cookie(cookie_file)
        if cookie_header is None and data.member_only:
            logger.error(f"[{data.id}] Member-only stream, but no cookies found. Cancelling")
            data.status = models.VTHellJobStatus.cancelled
            data.last_status = models.VTHellJobStatus.downloading
            data.error = "Members-only stream but there is no cookies file"
            await data.save()
            emit_data = {
                "id": data.id,
                "status": "CANCELLED",
                "error": "Members-only stream but there is no cookies file",
            }
            await app.wshandler.emit("job_update", emit_data)
            if app.first_process and app.ipc:
                await app.ipc.emit("ws_job_update", emit_data)
            return True, None

        twcast_id = data.id.replace("twcast-", "")
        try:
            twcast_info = await TwitcastingExtractor.process(
                f"https://twitcasting.tv/{data.channel_id}/movie/{twcast_id}", loop=app.loop
            )
        except ExtractorError as exc:
            logger.error(f"[{data.id}] {exc}", exc_info=exc)
            data.last_status = models.VTHellJobStatus.downloading
            message = exc.msg.lower()
            error_msg = f"Unable to extract information with yt-dlp ({exc.msg})"
            emit_data = {
                "id": data.id,
                "status": "ERROR",
                "error": error_msg,
            }
            if "private" in message or "captcha" or "geo restrict":
                data.status = models.VTHellJobStatus.cancelled
                emit_data["status"] = "CANCELLED"
            elif isinstance(exc.exc_info, yt_dlp.utils.ExtractorError):
                cause = exc.exc_info.msg.lower()
                if "members-only" in cause or "member-only" in cause:
                    data.status = models.VTHellJobStatus.cancelled
                    emit_data["status"] = "CANCELLED"
            else:
                data.status = models.VTHellJobStatus.error
            data.error = error_msg
            await data.save()
            await app.wshandler.emit("job_update", emit_data)
            if app.first_process and app.ipc:
                await app.ipc.emit("ws_job_update", emit_data)
            return True, None

        if twcast_info is None:
            return True, None

        temp_file = STREAMDUMP_PATH / f"{data.filename} [temp].mp4"
        resolution = twcast_info.urls[0].resolution
        logger.debug(f"[{data.id}] Downloading with resolution {resolution} format")
        data.resolution = resolution
        await data.save()

        http_headers = {}
        if cookie_header is not None:
            http_headers["Cookie"] = cookie_header
        ret_code, is_error, error_line = await download_via_ffmpeg(
            app, data, twcast_info.urls[0].url, temp_file, http_headers
        )
        if ret_code != 0 or is_error:
            logger.error(f"[{data.id}] ffmpeg exited with code {ret_code}")
            await DownloaderTasks.make_error(
                data,
                app,
                f"ffmpeg exited with code {ret_code}: {error_line}",
                models.VTHellJobStatus.downloading,
            )
            return True, None
        return False, temp_file

    @staticmethod
    async def download_twitch_stream(data: models.VTHellJob, app: SanicVTHell):
        if data.platform != "twitch":
            return True, None

        # If all number, assume VODs
        stream_url = f"https://twitch.tv/{data.channel_id}"
        if data.id.startswith("ttv-vod-"):
            vod_id = data.id.replace("ttv-vod-", "")
            stream_url = f"https://twitch.tv/videos/{vod_id}"

        ttv_stream = await TwitchExtractor.process(stream_url, loop=app.loop)
        if ttv_stream is None:
            return True, None

        temp_file = STREAMDUMP_PATH / f"{data.filename} [temp].ts"
        logger.debug(f"[{data.id}] Downloading with resolution {ttv_stream.resolution} format")

        save_fd = await aiofiles.open(str(temp_file), "wb+")
        is_errored = False
        error_line = None
        try:
            while True:
                try:
                    data = await ttv_stream.read()
                    if data == b"":
                        logger.debug(f"[{data.id}] Stream ended or connection got severed!")
                        break
                    await save_fd.write(data)
                except Exception as exc:
                    logger.error(f"[{data.id}] {exc}", exc_info=exc)
                    error_line = str(exc)
                    is_errored = True
                    break
        except asyncio.CancelledError:
            logger.debug(f"[{data.id}] Download cancelled")
            error_line = "Download cancelled"
            is_errored = True
        await save_fd.close()

        if is_errored:
            logger.error(f"[{data.id}] streamlink exited because {error_line}")
            await DownloaderTasks.make_error(
                data,
                app,
                f"streamlink exited because {error_line}",
                models.VTHellJobStatus.downloading,
            )
            return True, None
        return False, temp_file

    @staticmethod
    async def download_mildom_stream(data: models.VTHellJob, app: SanicVTHell):
        if data.platform != "mildom":
            return True, None

        cookie_file = await find_cookies_file()
        cookie_header = await read_and_parse_cookie(cookie_file)
        if cookie_header is None and data.member_only:
            logger.error(f"[{data.id}] Member-only stream, but no cookies found. Cancelling")
            data.status = models.VTHellJobStatus.cancelled
            data.last_status = models.VTHellJobStatus.downloading
            data.error = "Members-only stream but there is no cookies file"
            await data.save()
            emit_data = {
                "id": data.id,
                "status": "CANCELLED",
                "error": "Members-only stream but there is no cookies file",
            }
            await app.wshandler.emit("job_update", emit_data)
            if app.first_process and app.ipc:
                await app.ipc.emit("ws_job_update", emit_data)
            return True, None

        stream_url = f"https://www.mildom.com/{data.channel_id}"
        if data.id.startswith("mildom-vod-"):
            vod_id = data.id.replace("mildom-vod-", "")
            stream_url = f"https://www.mildom.com/playback/{data.channel_id}/{vod_id}"

        try:
            mildom_info = await MildomExtractor.process(stream_url, loop=app.loop)
        except ExtractorError as exc:
            logger.error(f"[{data.id}] {exc}", exc_info=exc)
            data.last_status = models.VTHellJobStatus.downloading
            message = exc.msg.lower()
            error_msg = f"Unable to extract information with yt-dlp ({exc.msg})"
            emit_data = {
                "id": data.id,
                "status": "ERROR",
                "error": error_msg,
            }
            if "private" in message or "captcha" or "geo restrict":
                data.status = models.VTHellJobStatus.cancelled
                emit_data["status"] = "CANCELLED"
            elif isinstance(exc.exc_info, yt_dlp.utils.ExtractorError):
                cause = exc.exc_info.msg.lower()
                if "members-only" in cause or "member-only" in cause:
                    data.status = models.VTHellJobStatus.cancelled
                    emit_data["status"] = "CANCELLED"
            else:
                data.status = models.VTHellJobStatus.error
            data.error = error_msg
            await data.save()
            await app.wshandler.emit("job_update", emit_data)
            if app.first_process and app.ipc:
                await app.ipc.emit("ws_job_update", emit_data)
            return True, None

        if mildom_info is None:
            return True, None

        temp_file = STREAMDUMP_PATH / f"{data.filename} [temp].ts"
        resolution = mildom_info.urls[0].resolution
        logger.debug(f"[{data.id}] Downloading with resolution {resolution} format")
        data.resolution = resolution
        await data.save()

        http_headers = {}
        if cookie_header is not None:
            http_headers["Cookie"] = cookie_header

        ret_code, is_error, error_line = await download_via_ffmpeg(
            app, data, mildom_info.urls[0].url, temp_file, http_headers
        )
        if ret_code != 0 or is_error:
            logger.error(f"[{data.id}] ffmpeg exited with code {ret_code}")
            await DownloaderTasks.make_error(
                data,
                app,
                f"ffmpeg exited with code {ret_code}: {error_line}",
                models.VTHellJobStatus.downloading,
            )
            return True, None
        return False, temp_file

    @staticmethod
    async def download_stream(data: models.VTHellJob, app: SanicVTHell):
        if data.platform == "youtube":
            logger.info(f"[{data.id}] Downloading youtube stream/video...")
            return await DownloaderTasks.download_stream_youtube(data, app)
        elif data.platform == "twitter":
            logger.info(f"[{data.id}] Downloading twitter spaces...")
            return await DownloaderTasks.download_stream_twitter_spaces(data, app)
        elif data.platform == "twitcasting":
            logger.info(f"[{data.id}] Downloading twitcasting stream...")
            return await DownloaderTasks.download_twitcasting_stream(data, app)
        elif data.platform == "twitch":
            logger.info(f"[{data.id}] Downloading twitch stream...")
            return await DownloaderTasks.download_twitch_stream(data, app)
        elif data.platform == "mildom":
            logger.info(f"[{data.id}] Downloading mildom stream...")
            return await DownloaderTasks.download_mildom_stream(data, app)
        logger.error(f"[{data.id}] Unsupported platform: {data.platform}")
        await DownloaderTasks.make_error(
            data,
            app,
            f"Unsupported platform: {data.platform}",
            models.VTHellJobStatus.downloading,
        )
        return True, None

    @staticmethod
    async def mux_rename_file(data: models.VTHellJob, app: SanicVTHell, temp_output: Path):
        if not await app.loop.run_in_executor(None, temp_output.exists):
            logger.error(f"[{data.id}] Temp file not found: {temp_output}")
            await DownloaderTasks.make_error(
                data,
                app,
                f"Temporary file not found: {temp_output}",
                models.VTHellJobStatus.muxing,
            )
            return True
        if data.platform == "twitter":
            logger.info(f"[{data.id}] Renaming file...")
            target_file = STREAMDUMP_PATH / f"{data.filename} [AAC].m4a"
            await app.loop.run_in_executor(None, temp_output.rename, target_file)
        return False

    @staticmethod
    async def mux_files(data: models.VTHellJob, app: SanicVTHell, temp_output: Optional[Path] = None):
        temp_output = temp_output or await find_temporary_file(data, app.loop)
        if temp_output is None:
            logger.warning(f"[{data.id}] No temporary file found, aborting.")
            await DownloaderTasks.make_error(
                data, app, "No temporary file found", models.VTHellJobStatus.muxing
            )
            return True
        if not await app.loop.run_in_executor(None, temp_output.exists):
            logger.warning(f"[{data.id}] downloaded file not found, skipping.")
            await DownloaderTasks.make_error(
                data, app, "Downloaded file not ofund", models.VTHellJobStatus.muxing
            )
            return True
        if data.platform not in ["youtube", "twitch", "twitcasting"]:
            logger.debug(f"[{data.id}] Got audio files, will not mux the file...")
            is_error = await DownloaderTasks.mux_rename_file(data, app, temp_output)
            return is_error
        logger.debug(f"[{data.id}] Will mux the following output: {temp_output}")
        mux_output = STREAMDUMP_PATH / f"{data.filename} [{data.resolution} AAC].mkv"
        mkvmerge_args = [app.config.MKVMERGE_PATH, "-o", str(mux_output), str(temp_output)]

        logger.debug(f"[{data.id}] Starting mkvmerge with args: {mkvmerge_args}")
        # Spawn mkvmerge
        try:
            mkvmerge_process = await asyncio.create_subprocess_exec(
                *mkvmerge_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
        except BlockingIOError as ioe:
            logger.error(f"[{data.id}] mkvmerge is blocking, aborting process now", exc_info=ioe)
            await DownloaderTasks.make_error(
                data,
                app,
                "mkvmerge is blocking, aborting process now",
                models.VTHellJobStatus.muxing,
            )
            return True
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
            await DownloaderTasks.make_error(
                data,
                app,
                f"mkvmerge exited with code {ret_code}:\n{stderr}",
                models.VTHellJobStatus.muxing,
            )
            return True
        return False

    @staticmethod
    async def determine_muxed_filename(data: models.VTHellJob):
        if data.platform in ["youtube", "twitch", "mildom"]:
            return STREAMDUMP_PATH / f"{data.filename} [{data.reso_or_na} AAC].mkv"
        elif data.platform == "twitter":
            return STREAMDUMP_PATH / f"{data.filename} [AAC].m4a"
        elif data.platform == "twitcasting":
            return STREAMDUMP_PATH / f"{data.filename} [XXXp AAC].mkv"
        return None

    @staticmethod
    async def upload_files(data: models.VTHellJob, app: SanicVTHell):
        mux_output = await DownloaderTasks.determine_muxed_filename(data)
        if mux_output is None:
            logger.warning(f"[{data.id}] muxed file not found, skipping.")
            return True
        if not await app.loop.run_in_executor(None, mux_output.exists):
            logger.warning(f"[{data.id}] muxed file not found, skipping.")
            return True

        base_folder = "Stream Archive"
        if data.member_only:
            base_folder = "Member-Only Stream Archive"
        joined_target = []
        joined_target = app.create_rclone_path(data.channel_id, "youtube")

        target_folder = build_rclone_path(app.config.RCLONE_DRIVE_TARGET, base_folder, *joined_target)
        announce_folder = build_rclone_path("mock:", base_folder, *joined_target).split("mock:", 1)[1]
        await DownloaderTasks.update_state(
            data,
            app,
            models.VTHellJobStatus.uploading,
            True,
            {
                "filename": mux_output.name,
                "path": announce_folder,
            },
        )
        rclone_args = [app.config.RCLONE_PATH, "-v", "-P", "copy", str(mux_output), target_folder]
        logger.debug(f"[{data.id}] Starting rclone with args: {rclone_args}")
        try:
            rclone_process = await asyncio.create_subprocess_exec(
                *rclone_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
        except BlockingIOError as ioe:
            logger.error(
                f"[{data.id}] rclone is blocking, aborting upload please do manual upload later!",
                exc_info=ioe,
            )
            await DownloaderTasks.make_error(
                data,
                app,
                "rclone is blocking, aborting upload please do manual upload later!",
                models.VTHellJobStatus.uploading,
            )
            return True
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
            await DownloaderTasks.make_error(
                data,
                app,
                f"rclone exited with code {ret_code}:\n{error_line}",
                models.VTHellJobStatus.uploading,
            )
            return True
        return False

    @staticmethod
    async def cleanup_files(data: models.VTHellJob, app: SanicVTHell, temp_output: Optional[Path] = None):
        mux_output = await DownloaderTasks.determine_muxed_filename(data)
        temp_output = temp_output or await find_temporary_file(data, app.loop)
        if temp_output is not None:
            try:
                logger.info(f"[{data.id}] Trying to delete temporary mp4 files...")
                await aiofiles.os.remove(str(temp_output))
            except Exception:
                logger.error(f"[{data.id}] Failed to delete temporary files, silently skipping")

        if app.config.RCLONE_DISABLE:
            logger.info(f"[{data.id}] Rclone is disabled, skipping muxed mkv deletion...")
            return
        if mux_output is not None:
            try:
                logger.info(f"[{data.id}] Trying to delete muxed mkv files...")
                await aiofiles.os.remove(str(mux_output))
            except Exception:
                logger.error(f"[{data.id}] Failed to delete muxed mkv files, silently skipping")

    @staticmethod
    async def propagate_error(data: models.VTHellJob, app: SanicVTHell):
        logger.info(f"[{data.id}] Trying to process error job.")
        if data.last_status == models.VTHellJobStatus.downloading:
            logger.info(f"[{data.id}][d] Last status was download job, trying to redo from download point.")
            # Reset to preparing
            await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.preparing)
            is_error, temp_output = await DownloaderTasks.download_stream(data, app)
            if is_error:
                logger.error(f"[{data.id}][d] Failed to redo stream download, aborting job.")
                return
            logger.info(f"[{data.id}][m] download job redone, continuing with muxing files...")
            is_error = await DownloaderTasks.mux_files(data, app, temp_output)
            if is_error:
                logger.error(f"[{data.id}][m] Failed to redo mux job, aborting.")
                return
            logger.info(f"[{data.id}][m] Mux job done, continuing with upload files...")
            if not app.config.RCLONE_DISABLE:
                is_error = await DownloaderTasks.upload_files(data, app)
                if is_error:
                    logger.error(f"[{data.id}][m] Failed to do upload job, aborting.")
                    return
                logger.info(f"[{data.id}][m] Upload job done, cleaning files...")
            else:
                logger.info(f"[{data.id}][m] Upload step skipped since Rclone is disabled...")
            await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.cleaning, True)
            await DownloaderTasks.cleanup_files(data, app, temp_output)
            logger.info(f"[{data.id}] Cleanup job done, marking job as finished!")
            data.status = models.VTHellJobStatus.done
            data.error = None
            data.last_status = None
            await data.save()
        elif data.last_status == models.VTHellJobStatus.muxing:
            logger.info(f"[{data.id}][m] Last status was mux job, trying to redo from mux point.")
            is_error = await DownloaderTasks.mux_files(data, app)
            if is_error:
                logger.error(f"[{data.id}][m] Failed to redo mux job, aborting.")
                return
            logger.info(f"[{data.id}][m] Mux job redone, continuing with upload files...")
            if not app.config.RCLONE_DISABLE:
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
            logger.info(f"[{data.id}][u] Last status was upload job, trying to redo from upload point.")
            if not app.config.RCLONE_DISABLE:
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
        data: models.VTHellJob,
        app: SanicVTHell,
        status: models.VTHellJobStatus,
        notify: bool = False,
        extras: Dict[str, Any] = {},
    ):
        data.status = status
        data.error = None
        data.last_status = None
        await data.save()
        data_update = {"id": data.id, "status": status.value}
        if extras:
            extras.pop("id", None)
            extras.pop("status", None)
            if extras:
                data_update.update(extras)
        await app.wshandler.emit("job_update", data_update)
        if app.first_process and app.ipc:
            await app.ipc.emit("ws_job_update", data_update)
        if notify:
            await app.dispatch(
                "internals.notifier.discord",
                context={"app": app, "data": data, "emit_type": "update"},
            )

    @staticmethod
    async def make_error(
        data: models.VTHellJob, app: SanicVTHell, error: str, last_status: models.VTHellJobStatus
    ):
        data.status = models.VTHellJobStatus.error
        data.last_status = last_status
        data.error = error
        data_update = {"id": data.id, "status": "ERROR", "error": error}
        await data.save()
        await app.wshandler.emit("job_update", data_update)
        if app.first_process and app.ipc:
            await app.ipc.emit("ws_job_update", data_update)

    @staticmethod
    async def executor(data: models.VTHellJob, time: int, task_name: str, app: SanicVTHell):
        logger.info(f"Executing job {data.id} (task {task_name})")
        grace_period = data.start_time - app.config.VTHELL_GRACE_PERIOD
        if time < grace_period:
            logger.info(f"Job {data.id} skipped since it's still far away from grace period")
            return

        if data.status != models.VTHellJobStatus.waiting:
            if data.status == models.VTHellJobStatus.error:
                await DownloaderTasks.propagate_error(data, app)
            else:
                logger.info(f"Job {data.id} skipped since it's being processed")
            return

        logger.info(f"Trying to start job {data.id}")
        await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.preparing)
        is_error, temp_output = await DownloaderTasks.download_stream(data, app)
        if is_error:
            return

        await DownloaderTasks.update_state(data, app, models.VTHellJobStatus.muxing, True)
        logger.info(f"Job {data.id} finished downloading, muxing into mkv files...")
        is_error = await DownloaderTasks.mux_files(data, app, temp_output)
        if is_error:
            return

        if not app.config.RCLONE_DISABLE:
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
        data_update = {"id": data.id, "status": "DONE"}
        await app.wshandler.emit("job_update", data_update)
        if app.first_process and app.ipc:
            await app.ipc.emit("ws_job_update", data_update)

        await DownloaderTasks.cleanup_files(data, app, temp_output)
        logger.info(f"Job {data.id} finished cleaning up, setting job as finished...")
        data.status = models.VTHellJobStatus.done
        data.error = None
        data.last_status = None
        await data.save()

    @staticmethod
    async def get_scheduled_job():
        try:
            all_jobs = await models.VTHellJob.all()
            all_jobs = list(
                filter(
                    lambda job: job.status
                    not in [models.VTHellJobStatus.done, models.VTHellJobStatus.cancelled],
                    all_jobs,
                )
            )
        except Exception as e:
            logger.error(f"Failed to get scheduled jobs: {e}", exc_info=e)
            return []
        return all_jobs

    @classmethod
    async def main_loop(cls: Type[DownloaderTasks], app: SanicVTHell):
        if not app.first_process:
            logger.warning("Downloader is not running in the first process, skipping it")
            return
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
