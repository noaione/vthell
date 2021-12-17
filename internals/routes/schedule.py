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

import logging
from typing import TYPE_CHECKING

import pendulum
from sanic import Blueprint
from sanic.request import Request
from sanic.response import json

from internals.db import models
from internals.decorator import secure_access
from internals.utils import secure_filename

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

bp_sched = Blueprint("api_scheduler", url_prefix="/api")
logger = logging.getLogger("Routes.API.Schedule")


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
    if holodex is None:
        return json({"error": "Holodex API is not ready"}, status=500)
    if not holodex.ready:
        return json({"error": "Holodex API is not ready"}, status=500)

    if "id" not in json_request:
        return json({"error": "Missing `id` in json request"}, status=400)

    video_id = json_request["id"]
    logger.info(f"ScheduleRequest: Received request for video {video_id}")
    existing_job = await models.VTHellJob.get_or_none(id=video_id)

    video_res = await holodex.get_video(video_id)
    if video_res is None:
        logger.error(f"ScheduleRequest: Video {video_id} not found")
        return json({"error": "Video not found"}, status=404)

    title_safe = secure_filename(video_res.title)
    utc_unix = pendulum.from_timestamp(video_res.start_time, tz="UTC")
    as_jst = utc_unix.in_timezone("Asia/Tokyo")
    filename = f"[{as_jst.year}.{as_jst.month}.{as_jst.day}.{video_res.id}] {title_safe}"
    if existing_job is not None:
        logger.info(f"ScheduleRequest: Video {video_id} already exists, merging data...")
        existing_job.title = video_res.title
        existing_job.filename = filename
        existing_job.start_time = video_res.start_time
        existing_job.member_only = video_res.is_member
        await existing_job.save()
        await app.wshandler.emit(
            "job_update",
            {
                "id": existing_job.id,
                "title": existing_job.title,
                "start_time": existing_job.start_time,
                "channel_id": existing_job.channel_id,
                "is_member": existing_job.member_only,
                "status": existing_job.status.value,
            },
        )
    else:
        logger.info(f"ScheduleRequest: Video {video_id} not found, creating new job...")
        job_request = models.VTHellJob(
            id=video_res.id,
            title=video_res.title,
            filename=filename,
            start_time=video_res.start_time,
            channel_id=video_res.channel_id,
            member_only=video_res.is_member,
        )
        await job_request.save()
        await app.wshandler.emit(
            "job_scheduled",
            {
                "id": job_request.id,
                "title": job_request.title,
                "filename": job_request.filename,
                "start_time": job_request.start_time,
                "channel_id": job_request.channel_id,
                "is_member": job_request.member_only,
                "status": job_request.status.value,
                "resolution": job_request.resolution,
                "error": job_request.error,
            },
        )
    logger.info(f"APIAdd: Video {video_id} added to queue, sending back request")
    return json(video_res.to_json())


@bp_sched.delete("/schedule/<video_id>")
@secure_access
async def delete_job(request: Request, video_id: str):
    app: SanicVTHell = request.app
    await app.wait_until_ready()
    logger.info("ScheduleDelete: Received request for video <%s>", video_id)
    job = await models.VTHellJob.get_or_none(id=video_id)
    if job is None:
        logger.error("ScheduleDelete: Video <%s> not found", video_id)
        return json({"error": "Video not found"}, status=404)
    if job.status not in [
        models.VTHellJobStatus.cleaning,
        models.VTHellJobStatus.done,
        models.VTHellJobStatus.waiting,
    ]:
        return json({"error": "Current video status does not allow you to delete video"}, status=406)

    await job.delete()
    await app.wshandler.emit("job_delete", {"id": video_id})
    return json(
        {
            "id": job.id,
            "title": job.title,
            "filename": job.filename,
            "start_time": job.start_time,
            "channel_id": job.channel_id,
            "is_member": job.member_only,
            "status": job.status,
            "error": job.error,
        }
    )
