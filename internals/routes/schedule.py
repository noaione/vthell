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

import logging
from typing import TYPE_CHECKING, Union

import pendulum
from sanic import Blueprint
from sanic.response import json

from internals.db import models
from internals.decorator import secure_access
from internals.utils import map_to_boolean, secure_filename

if TYPE_CHECKING:
    from sanic.request import Request

    from internals.holodex import HolodexVideo
    from internals.ihaapi import ihaAPIVideo
    from internals.vth import SanicVTHell

bp_sched = Blueprint("api_scheduler", url_prefix="/api")
logger = logging.getLogger("Routes.API.Schedule")


def prefix_id_platform(data: Union[HolodexVideo, ihaAPIVideo]):
    video_id = data.id
    if data.platform == "twitch":
        return f"ttv-stream-{video_id}"
    elif data.platform == "twitcasting":
        return f"twcast-{video_id}"
    elif data.platform == "twitter":
        return f"twtsp-{video_id}"
    return video_id


@bp_sched.post("/schedule")
@secure_access
async def add_new_jobs(request: Request):
    app: SanicVTHell = request.app
    await app.wait_until_ready()
    try:
        json_request = request.json
    except Exception as cep:
        logger.error("Error while parsing request: %s", cep, exc_info=cep)
        return json({"error": "Invalid JSON"}, status=400)
    holodex = app.holodex
    ihaapi = app.ihaapi

    platform = "youtube"
    if "id" not in json_request:
        return json({"error": "Missing `id` in json request"}, status=400)
    if "platform" in json_request:
        if json_request["platform"] in ["youtube", "twitch", "twitcasting", "twitter"]:
            platform = json_request["platform"]

    video_id = json_request["id"]
    logger.info(f"ScheduleRequest: Received request for video {video_id}")
    if platform == "youtube":
        video_res = await holodex.get_video(video_id)
        if video_res is None:
            logger.error(f"ScheduleRequest(Holodex): Video {video_id} not found")
            return json({"error": "Video not found or invalid (via Holodex)"}, status=404)
    else:
        video_res = await ihaapi.get_video(video_id, platform)
        if video_res is None:
            logger.error(f"ScheduleRequest(ihaAPI): Video {video_id} not found")
            return json({"error": "Video not found or invalid (via ihateani.me API)"}, status=404)

    title_safe = secure_filename(video_res.title)
    utc_unix = pendulum.from_timestamp(video_res.start_time, tz="UTC")
    as_jst = utc_unix.in_timezone("Asia/Tokyo")
    bideo_id = video_res.id
    if video_res.platform == "twitch":
        bideo_id = video_res.channel_id
    video_id_actual = prefix_id_platform(video_res)
    existing_job = await models.VTHellJob.get_or_none(id=video_id_actual)
    filename = f"[{as_jst.year}.{as_jst.month}.{as_jst.day}.{bideo_id}] {title_safe}"
    if existing_job is not None:
        logger.info(f"ScheduleRequest: Video {video_id_actual} already exists, merging data...")
        existing_job.title = video_res.title
        existing_job.filename = filename
        existing_job.start_time = video_res.start_time
        existing_job.member_only = video_res.is_member
        if existing_job.status == models.VTHellJobStatus.error:
            last_status = existing_job.last_status
            if last_status in [models.VTHellJobStatus.downloading, models.VTHellJobStatus.preparing]:
                existing_job.status = models.VTHellJobStatus.waiting
                existing_job.last_status = None
                existing_job.error = None
        elif existing_job.status == models.VTHellJobStatus.cancelled:
            existing_job.last_status = None
            existing_job.error = None
            existing_job.status = models.VTHellJobStatus.waiting
        await existing_job.save()
        job_update_data = {
            "id": existing_job.id,
            "title": existing_job.title,
            "start_time": existing_job.start_time,
            "channel_id": existing_job.channel_id,
            "is_member": existing_job.member_only,
            "status": existing_job.status.value,
        }
        await app.wshandler.emit("job_update", job_update_data)
        if app.first_process and app.ipc:
            await app.ipc.emit("ws_job_update", job_update_data)
    else:
        logger.info(f"ScheduleRequest: Video {video_id_actual} not found, creating new job...")
        job_request = models.VTHellJob(
            id=video_id_actual,
            title=video_res.title,
            filename=filename,
            start_time=video_res.start_time,
            channel_id=video_res.channel_id,
            member_only=video_res.is_member,
            platform=video_res.platform,
        )
        await job_request.save()
        job_data_update = {
            "id": job_request.id,
            "title": job_request.title,
            "filename": job_request.filename,
            "start_time": job_request.start_time,
            "channel_id": job_request.channel_id,
            "is_member": job_request.member_only,
            "status": job_request.status.value,
            "resolution": job_request.resolution,
            "platform": job_request.platform.value,
            "error": job_request.error,
        }
        await app.wshandler.emit("job_scheduled", job_data_update)
        if app.first_process and app.ipc:
            await app.ipc.emit("ws_job_scheduled", job_data_update)
    logger.info(f"APIAdd: Video {video_id} added to queue, sending back request")
    return json(video_res.to_json())


@bp_sched.delete("/schedule/<video_id>")
@secure_access
async def delete_job(request: Request, video_id: str):
    app: SanicVTHell = request.app
    await app.wait_until_ready()
    force_delete = map_to_boolean(request.args.get("force", "0"))
    logger.info("ScheduleDelete: Received request for video <%s>", video_id)
    job = await models.VTHellJob.get_or_none(id=video_id)
    if job is None:
        logger.error("ScheduleDelete: Video <%s> not found", video_id)
        return json({"error": "Video not found"}, status=404)
    if (
        job.status
        not in [
            models.VTHellJobStatus.cleaning,
            models.VTHellJobStatus.done,
            models.VTHellJobStatus.waiting,
            models.VTHellJobStatus.error,
            models.VTHellJobStatus.cancelled,
        ]
        and not force_delete
    ):
        return json({"error": "Current video status does not allow you to delete video"}, status=406)

    await job.delete()
    await app.wshandler.emit("job_delete", {"id": video_id})
    if app.first_process and app.ipc:
        await app.ipc.emit("ws_job_delete", {"id": video_id})
    return json(
        {
            "id": job.id,
            "title": job.title,
            "filename": job.filename,
            "start_time": job.start_time,
            "channel_id": job.channel_id,
            "is_member": job.member_only,
            "status": job.status.value,
            "platform": job.platform.value,
            "error": job.error,
        }
    )
