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

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json

from internals.db import models
from internals.utils import map_to_boolean

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

bp_status = Blueprint("api_status", url_prefix="/api")
logger = logging.getLogger("Routes.API.Status")


@bp_status.get("/status")
async def existing_jobs(request: Request):
    app: SanicVTHell = request.app
    include_done = False
    try:
        should_include = request.args["include_done"]
        if isinstance(should_include, list):
            should_include = should_include[0]
        include_done = map_to_boolean(should_include)
    except KeyError:
        pass
    await app.wait_until_ready()

    if include_done:
        jobs = await models.VTHellJob.all()
    else:
        jobs = await models.VTHellJob.exclude(status=models.VTHellJobStatus.done)

    as_json_fmt = []
    for job in jobs:
        as_json_fmt.append(
            {
                "id": job.id,
                "title": job.title,
                "start_time": job.start_time,
                "channel_id": job.channel_id,
                "is_member": job.member_only,
                "status": job.status.value,
                "platform": job.platform.value,
                "error": job.error,
            }
        )
    return json(as_json_fmt)


@bp_status.get("/status/<id:str>")
async def existing_single_job(request: Request, id: str):
    app: SanicVTHell = request.app
    await app.wait_until_ready()

    job = await models.VTHellJob.get_or_none(id=id)
    if job is None:
        return json({"error": "Job not found."}, status=404)

    return json(
        {
            "id": job.id,
            "title": job.title,
            "start_time": job.start_time,
            "channel_id": job.channel_id,
            "is_member": job.member_only,
            "status": job.status.value,
            "platform": job.platform.value,
            "error": job.error,
        }
    )
