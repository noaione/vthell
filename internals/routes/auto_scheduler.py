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
from sanic.response import empty, json

from internals.db import models
from internals.decorator import secure_access
from internals.utils import map_to_boolean

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

bp_autosched = Blueprint("api_autoscheduler", url_prefix="/api")
logger = logging.getLogger("Routes.API.AutoScheduler")


@bp_autosched.get("/auto-scheduler")
async def get_auto_scheduler(request: Request):
    """
    Get the auto scheduler status.
    """
    app: SanicVTHell = request.app
    await app.wait_until_ready()
    all_auto_scheduler = await models.VTHellAutoScheduler.all()

    enabled_scheduler = list(filter(lambda x: x.include, all_auto_scheduler))
    disabled_scheduler = list(filter(lambda x: not x.include, all_auto_scheduler))

    enabled_u = []
    for sched in enabled_scheduler:
        enabled_u.append(
            {
                "id": sched.pk,
                "type": sched.type.name,
                "data": sched.data,
                "chains": sched.chains,
            }
        )
    disabled_u = []
    for sched in disabled_scheduler:
        disabled_u.append(
            {
                "id": sched.pk,
                "type": sched.type.name,
                "data": sched.data,
                "chains": sched.chains,
            }
        )

    return json(
        {
            "include": enabled_u,
            "exclude": disabled_u,
        }
    )


@bp_autosched.post("/auto-scheduler")
@secure_access
async def post_auto_scheduler(request: Request):
    """
    Add a new auto scheduler.
    """
    app: SanicVTHell = request.app
    try:
        json_request = request.json
    except Exception as cep:
        logger.error("Error while parsing request: %s", cep, exc_info=cep)
        return json({"error": "Invalid JSON"}, status=400)
    await app.wait_until_ready()

    ctype = json_request.get("type")
    data = json_request.get("data")
    include = json_request.get("include", True)
    chains_new = json_request.get("chains")

    if not isinstance(include, bool):
        include = map_to_boolean(include)

    if not ctype:
        return json({"error": "Missing type"}, status=400)
    if not data:
        return json({"error": "Missing data"}, status=400)

    if not isinstance(data, str):
        return json({"error": "Invalid data format, must be a string"}, status=400)

    data = data.strip()
    if data == "":
        return json({"error": "Invalid data format, cannot be empty"}, status=400)

    ctype_enum = models.VTHellAutoType.from_name(ctype)
    if ctype_enum is None:
        return json({"error": "Invalid type, must be `channel`, `group`, `word`, `regex_word`"}, status=400)

    chains = None
    if ctype in [models.VTHellAutoType.word, models.VTHellAutoType.regex_word] and isinstance(
        chains_new, (dict, list)
    ):
        valid_chains = []
        if isinstance(chains_new, dict):
            if "type" not in chains_new:
                return json({"error": "Missing type for single chains"}, status=400)
            elif "data" not in chains_new:
                return json({"error": "Missing data for single chains"}, status=400)
            validate_type = models.VTHellAutoType.from_name(chains_new["type"])
            if validate_type is None:
                return json({"error": "Invalid type for single chains"}, status=400)
            valid_chains.append({"type": validate_type.name, "data": chains_new["data"]})
        else:
            for x, chain in enumerate(chains_new):
                if not isinstance(chain, dict):
                    continue
                if "type" not in chain:
                    return json({"error": f"Missing type for chains.{x}"}, status=400)
                elif "data" not in chain:
                    return json({"error": f"Missing data for chains.{x}"}, status=400)
                validate_type = models.VTHellAutoType.from_name(chain["type"])
                if validate_type is None:
                    return json({"error": f"Invalid type for chains.{x}"}, status=400)
                valid_chains.append({"type": validate_type.name, "data": chain["data"]})
        chains = valid_chains.copy()
    auto_sched = models.VTHellAutoScheduler(
        type=ctype_enum,
        data=data,
        include=include,
        chains=chains,
    )
    await auto_sched.save()
    return json(
        {
            "id": auto_sched.pk,
            "type": auto_sched.type.name,
            "data": auto_sched.data,
            "chains": auto_sched.chains,
        }
    )


@bp_autosched.patch("/auto-scheduler/<id:int>")
@secure_access
async def patch_auto_scheduler(request: Request, id: int):
    """
    Patch a single auto scheduler
    """

    app: SanicVTHell = request.app
    try:
        json_request = request.json
    except Exception as cep:
        logger.error("Error while parsing request: %s", cep, exc_info=cep)
        return json({"error": "Invalid JSON"}, status=400)
    await app.wait_until_ready()
    all_auto_scheduler = await models.VTHellAutoScheduler.all()

    sched = list(filter(lambda x: x.pk == id, all_auto_scheduler))

    if len(sched) == 0:
        return json({"error": "Auto Scheduler not found"}, status=404)

    sched = sched[0]

    update_data = json_request.get("data")
    update_type = json_request.get("type")
    update_enable = json_request.get("include")
    update_chains = json_request.get("chains")
    if update_type is not None:
        update_type = models.VTHellAutoType.from_name(update_type)

    if update_data is None and update_type is None and update_enable is None and update_chains is None:
        return json(
            {"error": "No data will be changed, please make sure you're providing the correct data"},
            status=400,
        )

    is_chain_update_only = False
    if update_data is None and update_type is None and update_enable is None and update_chains is not None:
        is_chain_update_only = True

    if update_type is not None:
        sched.type = update_type
    if update_data is not None:
        sched.data = update_data
    if update_enable is not None:
        sched.include = update_enable
    chain_updated = False
    if sched.type in [models.VTHellAutoType.word, models.VTHellAutoType.regex_word] and isinstance(
        update_chains, (dict, list)
    ):
        valid_chains = []
        if isinstance(update_chains, dict):
            if "type" not in update_chains:
                return json({"error": "Missing type for single chains"}, status=400)
            elif "data" not in update_chains:
                return json({"error": "Missing data for single chains"}, status=400)
            validate_type = models.VTHellAutoType.from_name(update_chains["type"])
            if validate_type is None:
                return json({"error": "Invalid type for single chains"}, status=400)
            valid_chains.append({"type": validate_type.name, "data": update_chains["data"]})
        else:
            for x, chain in enumerate(update_chains):
                if not isinstance(chain, dict):
                    continue
                if "type" not in chain:
                    return json({"error": f"Missing type for chains.{x}"}, status=400)
                elif "data" not in chain:
                    return json({"error": f"Missing data for chains.{x}"}, status=400)
                validate_type = models.VTHellAutoType.from_name(chain["type"])
                if validate_type is None:
                    return json({"error": f"Invalid type for chains.{x}"}, status=400)
                valid_chains.append({"type": validate_type.name, "data": chain["data"]})
        if len(valid_chains) > 0:
            chain_updated = True
            sched.chains = valid_chains
    if is_chain_update_only and not chain_updated:
        return json({"error": "No valid chains can be used to update"}, status=400)
    await sched.save()
    return empty()


@bp_autosched.delete("/auto-scheduler/<id:int>")
@secure_access
async def delete_auto_scheduler(request: Request, id: int):
    """
    Delete a single auto scheduler
    """

    app: SanicVTHell = request.app
    await app.wait_until_ready()
    all_auto_scheduler = await models.VTHellAutoScheduler.all()

    sched = list(filter(lambda x: x.pk == id, all_auto_scheduler))

    if len(sched) == 0:
        return json({"error": "Auto Scheduler not found"}, status=404)

    sched = sched[0]

    await sched.delete()
    return json({"id": sched.pk, "data": sched.data, "type": sched.type.name})
