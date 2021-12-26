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

import argparse
import asyncio
import os
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import ZipFile

import requests
from dotenv import load_dotenv
from sanic.config import DEFAULT_CONFIG
from sanic.response import text
from sanic_cors import CORS
from tortoise import Tortoise

from internals.constants import archive_gh, hash_gh
from internals.db import models, register_db
from internals.db.ipc import IPCServerClientBridge
from internals.discover import autodiscover
from internals.holodex import HolodexAPI
from internals.logme import setup_logger
from internals.monke import monkeypatch_sanic_runner
from internals.utils import (
    find_ffmpeg_binary,
    find_mkvmerge_binary,
    find_rclone_binary,
    find_ytarchive_binary,
    map_to_boolean,
    test_ffmpeg_binary,
    test_mkvmerge_binary,
    test_rclone_binary,
    test_ytarchive_binary,
)
from internals.vth import SanicVTHell, SanicVTHellConfig

if TYPE_CHECKING:
    from sanic.request import Request

monkeypatch_sanic_runner()
CURRENT_PATH = Path(__file__).absolute().parent
logger = setup_logger(CURRENT_PATH / "logs")
load_dotenv(str(CURRENT_PATH / ".env"))

PORT = os.getenv("PORT")
if PORT is None:
    PORT = 12790
else:
    PORT = int(PORT)


async def after_server_starting(app: SanicVTHell, loop: asyncio.AbstractEventLoop):
    if os.name != "nt":
        logger.info("Attaching the IPC server and client")
        app.ipc = IPCServerClientBridge()
        app.ipc.attach(app)


async def after_server_closing(app: SanicVTHell, loop: asyncio.AbstractEventLoop):
    logger.info("Closing DB client")
    await Tortoise.close_connections()
    logger.info("Closing Holodex API")
    if app.holodex:
        await app.holodex.close()
    logger.info("Closing WSHandler")
    app.wshandler.close()
    if app.ipc:
        logger.info("Closing IPC server and client")
        app.ipc.close()
        if app.first_process:
            logger.info("Cleaning up IPC server file...")
            await asyncio.sleep(2)
            try:
                await loop.run_in_executor(None, os.remove, str(app.ipc.ipc_path))
            except Exception as err:
                logger.error("Failed to clean up IPC server file", exc_info=err)
    logger.info("Extras are all cleanup!")


def init_dataset():
    dataset_folder = CURRENT_PATH / "dataset"
    hash_file = dataset_folder / "currentversion"
    if dataset_folder.exists():
        if hash_file.exists():
            logger.info("Dataset folder exists, and hash file exists")
            return
        logger.info("Dataset folder exists, but hash file does not exist")

    logger.info("Dataset folder does not exist, creating it")
    dataset_folder.mkdir(parents=True, exist_ok=True)
    logger.info("Dataset folder created, downloading archive...")

    archives = requests.get(archive_gh)
    archive_binary = BytesIO()
    archive_binary.write(archives.content)
    archive_binary.seek(0)

    logger.info("Archive downloaded, extracting...")
    with ZipFile(archive_binary) as zip:
        for file in zip.filelist:
            fp_path = dataset_folder / file.filename
            with open(str(fp_path), "wb") as fp:
                fp.write(zip.read(file))

    logger.info("Extracted, writing hash file")
    remote_hash = requests.get(hash_gh).text.splitlines()[0].strip()
    with open(str(hash_file), "w") as fp:
        fp.write(remote_hash)

    logger.info("Hash file written, dataset initialized")


def load_config():
    config = {}
    config["VTHELL_DB"] = os.getenv("VTHELL_DB", "vth.db")
    config["VTHELL_LOOP_DOWNLOADER"] = os.getenv("VTHELL_LOOP_DOWNLOADER", "60")
    config["VTHELL_LOOP_SCHEDULER"] = os.getenv("VTHELL_LOOP_SCHEDULER", "180")
    config["VTHELL_GRACE_PERIOD"] = os.getenv("VTHELL_GRACE_PERIOD", "120")
    config["HOLODEX_API_KEY"] = os.getenv("HOLODEX_API_KEY")
    if not isinstance(config["VTHELL_LOOP_DOWNLOADER"], (int, float)):
        try:
            config["VTHELL_LOOP_DOWNLOADER"] = int(config["VTHELL_LOOP_DOWNLOADER"])
        except ValueError:
            config["VTHELL_LOOP_DOWNLOADER"] = 60
            logger.error(
                "VTHELL_LOOP_DOWNLOADER must be a number, not %s (fallback to 60s)",
                config["VTHELL_LOOP_DOWNLOADER"],
            )
    if not isinstance(config["VTHELL_LOOP_SCHEDULER"], (int, float)):
        try:
            config["VTHELL_LOOP_SCHEDULER"] = int(config["VTHELL_LOOP_SCHEDULER"])
        except ValueError:
            config["VTHELL_LOOP_SCHEDULER"] = 180
            logger.error(
                "VTHELL_LOOP_SCHEDULER must be a number, not %s (fallback to 180s)",
                config["VTHELL_LOOP_SCHEDULER"],
            )
    if not isinstance(config["VTHELL_GRACE_PERIOD"], (int, float)):
        try:
            config["VTHELL_GRACE_PERIOD"] = int(config["VTHELL_GRACE_PERIOD"])
        except ValueError:
            config["VTHELL_GRACE_PERIOD"] = 120
            logger.error(
                "VTHELL_GRACE_PERIOD must be a number, not %s (fallback to 120s)",
                config["VTHELL_GRACE_PERIOD"],
            )

    config["WEBSERVER_REVERSE_PROXY"] = map_to_boolean(os.getenv("WEBSERVER_REVERSE_PROXY", "false"))
    config["WEBSERVER_REVERSE_PROXY_SECRET"] = os.getenv("WEBSERVER_REVERSE_PROXY_SECRET", "")
    config["WEBSERVER_PASSWORD"] = os.getenv("WEBSERVER_PASSWORD", "")

    ytarchive_path = os.getenv("YTARCHIVE_BINARY", "") or find_ytarchive_binary()
    rclone_path = os.getenv("RCLONE_BINARY", "") or find_rclone_binary()
    mkvmerge_path = os.getenv("MKVMERGE_BINARY", "") or find_mkvmerge_binary()
    rclone_drive_target = os.getenv("RCLONE_DRIVE_TARGET", "")
    rclone_disable = map_to_boolean(os.getenv("RCLONE_DISABLE", "0"))
    if not rclone_disable and not test_rclone_binary(rclone_path, rclone_drive_target):
        logger.error("Either RClone binary or the drive target is not valid")
        raise FileNotFoundError("Rclone binary not found")
    config["RCLONE_PATH"] = rclone_path
    config["RCLONE_DRIVE_TARGET"] = rclone_drive_target
    config["RCLONE_DISABLE"] = rclone_disable
    if not test_ytarchive_binary(ytarchive_path):
        logger.error(
            "YTArchive binary not found, please download here: https://github.com/Kethsar/ytarchive/releases"
        )
        raise FileNotFoundError("YTArchive binary not found")
    config["YTARCHIVE_PATH"] = ytarchive_path
    if not test_mkvmerge_binary(mkvmerge_path):
        logger.error("MKVMerge binary not found, please install mkvtoolnix (windows) or mkvmerge first!")
        raise FileNotFoundError("MKVMerge binary not found")
    config["MKVMERGE_PATH"] = mkvmerge_path
    ffmpeg_path = os.getenv("FFMPEG_BINARY", "")
    if not test_ffmpeg_binary(ffmpeg_path):
        ffmpeg_path = find_ffmpeg_binary()
        if ffmpeg_path is not None:
            if not test_ffmpeg_binary(ffmpeg_path):
                logger.error("FFMpeg binary not found, please install ffmpeg first!")
                raise FileNotFoundError("FFMpeg binary not found")
            else:
                ffmpeg_path = Path(ffmpeg_path)
                PATH = os.environ.get("PATH", "")
                os.environ["PATH"] = str(ffmpeg_path.absolute().parent) + os.pathsep + PATH
        else:
            logger.error("FFMpeg binary not found, please install ffmpeg first!")
            raise FileNotFoundError("FFMpeg binary not found")
    config["FFMPEG_PATH"] = ffmpeg_path

    # Notification
    config["NOTIFICATION_DISCORD_WEBHOOK"] = os.getenv("NOTIFICATION_DISCORD_WEBHOOK")
    return config


def setup_app():
    logger.info("Initializing Sanic app...")
    init_dataset()
    DISCOVERY_MODULES = ["internals.routes", "internals.tasks", "internals.notifier", "internals.chat"]
    config = SanicVTHellConfig(defaults=DEFAULT_CONFIG, load_env=False)
    config.update_config(load_config())
    db_modules = {"models": ["internals.db.models", "aerich.models"]}

    app = SanicVTHell("VTHell", config=config)
    CORS(app, origins=["*"])
    config._app = app
    logger.info("Registering DB client")
    register_db(app, modules=db_modules, generate_schemas=True)
    logger.info("Attaching Holodex to Sanic")
    HolodexAPI.attach(app)
    logger.info("Registering Sanic middlewares and extra routes")
    app.after_server_start(after_server_starting)
    app.after_server_stop(after_server_closing)

    @app.route("/", methods=["GET", "HEAD"])
    async def index(request: Request):
        if request.method == "HEAD":
            return text("")
        return text("</>")

    async def on_connect_ws(sid: str, ws):
        logger.info("Client connected: %s", sid)
        await app.wait_until_ready()
        active_jobs = await models.VTHellJob.exclude(status=models.VTHellJobStatus.done)
        as_json_fmt = []
        for job in active_jobs:
            as_json_fmt.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "filename": job.filename,
                    "start_time": job.start_time,
                    "channel_id": job.channel_id,
                    "is_member": job.member_only,
                    "status": job.status.value,
                    "resolution": job.resolution,
                    "error": job.error,
                }
            )
        logger.info("Sending active jobs to client %s", sid)
        await app.wshandler.emit("connect_job_init", as_json_fmt, to=sid)

    app.wshandler.on("connect", on_connect_ws)

    logger.info("Auto discovering routes, tasks and more...")
    autodiscover(app, *DISCOVERY_MODULES, recursive=True)
    app.config.WEBSOCKET_MAX_SIZE = 2 ** 20
    app.config.WEBSOCKET_MAX_QUEUE = 32
    app.config.WEBSOCKET_READ_LIMIT = 2 ** 16
    app.config.WEBSOCKET_WRITE_LIMIT = 2 ** 16
    app.config.WEBSOCKET_PING_INTERVAL = None  # Disable, use custom ping
    app.config.WEBSOCKET_PING_TIMEOUT = 30
    app.enable_websocket()

    logger.info("Sanic is now ready to be fast!")
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-P", "--port", type=int, help="Port to listen on", default=PORT)
    parser.add_argument("-D", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("-H", "--host", help="Host to listen on", default="127.0.0.1")
    parser.add_argument("-W", "--workers", help="Number of worker to be used", default=1, type=int)
    parser.add_argument("-u", "--uds", help="Unix socket to listen on", default=None)
    args = parser.parse_args()

    logger.info(f"Starting VTHell server at port {args.port}...")
    app = setup_app()
    defaults = {
        "debug": args.debug,
        "access_log": args.debug,
        "workers": args.workers,
    }

    if args.uds is not None:
        app.run(unix=args.uds, **defaults)
    else:
        app.run(host=args.host, port=args.port, **defaults)
