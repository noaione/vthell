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

import asyncio
import os
from pathlib import Path

import socketio
from dotenv import load_dotenv
from tortoise import Tortoise
from sanic.config import DEFAULT_CONFIG
from sanic.response import text
from sanic_cors import CORS

from internals.db.client import register_db
from internals.discover import autodiscover
from internals.holodex import HolodexAPI
from internals.logme import setup_logger
from internals.utils import (
    find_mkvmerge_binary,
    find_rclone_binary,
    find_ytarchive_binary,
    map_to_boolean,
    test_mkvmerge_binary,
    test_rclone_binary,
    test_ytarchive_binary,
)
from internals.vth import SanicVTHell, SanicVTHellConfig

CURRENT_PATH = Path(__file__).absolute().parent
logger = setup_logger(CURRENT_PATH / "logs")
load_dotenv(str(CURRENT_PATH / ".env"))

PORT = os.getenv("PORT")
if PORT is None:
    PORT = 12790
else:
    PORT = int(PORT)


async def after_server_closing(app: SanicVTHell, loop: asyncio.AbstractEventLoop):
    logger.info("Closing DB client")
    await Tortoise.close_connections()
    logger.info("Closing Holodex API")
    if app.holodex:
        await app.holodex.close()
    logger.info("Extras are all cleanup!")


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
    if not test_rclone_binary(rclone_path, rclone_drive_target):
        logger.error("Either RClone binary or the drive target is not valid")
        raise FileNotFoundError("Rclone binary not found")
    config["RCLONE_PATH"] = rclone_path
    config["RCLONE_DRIVE_TARGET"] = rclone_drive_target
    if not test_ytarchive_binary(ytarchive_path):
        logger.error(
            "YTArchive binary not found, please download here: https://github.com/Kethsar/ytarchive/releases"
        )
        raise FileNotFoundError("YTArchive binary not found")
    if not test_mkvmerge_binary(mkvmerge_path):
        logger.error("MKVMerge binary not found, please install mkvtoolnix (windows) or mkvmerge first!")
        raise FileNotFoundError("MKVMerge binary not found")
    config["MKVMERGE_PATH"] = mkvmerge_path
    return config


def setup_app():
    config = SanicVTHellConfig(defaults=DEFAULT_CONFIG, load_env=False)
    config.update_config(load_config())
    asgi_mode = os.getenv("SERVER_GATEWAY_INTERFACE") == "ASGI_MODE"
    sio = socketio.AsyncServer(async_mode="sanic" if not asgi_mode else "asgi", cors_allowed_origins="*")
    if asgi_mode:
        sanic_app = SanicVTHell("VTHell", config=config)
        CORS(sanic_app, origins=["*"])
        logger.info("Attaching Socket.IO to Sanic")
        app = socketio.ASGIApp(sio, sanic_app)
        config._app = sanic_app
        sanic_app.sio = sio
        logger.info("Attaching Holodex to Sanic")
        HolodexAPI.attach(sanic_app)
        sanic_app.after_server_stop(after_server_closing)
        logger.info("Registering DB client")
        register_db(sanic_app, modules={"models": ["internals.db.models"]}, generate_schemas=True)
        logger.info("Trying to auto-discover routes, tasks, and more...")
        autodiscover(sanic_app, "internals.routes", "internals.tasks", recursive=True)

        @sanic_app.route("/")
        async def index(request):
            return text("</>")

    else:
        config["CORS_SUPPORTS_CREDENTIALS"] = True
        app = SanicVTHell("VTHell", config=config)
        CORS(app, origins=["*"])
        config._app = app
        logger.info("Attaching Socket.IO to Sanic")
        sio.attach(app)
        app.sio = sio
        logger.info("Attaching Holodex to Sanic")
        HolodexAPI.attach(app)
        app.after_server_stop(after_server_closing)

        logger.info("Registering DB client")
        register_db(app, modules={"models": ["internals.db.models"]}, generate_schemas=True)
        logger.info("Trying to auto-discover routes, tasks, and more...")
        autodiscover(app, "internals.routes", "internals.tasks", recursive=True)

        @app.route("/")
        async def index(request):
            return text("</>")

    return app


if __name__ == "__main__":
    logger.info(f"Starting VTHell server at port {PORT}...")
    os.environ.setdefault("SERVER_GATEWAY_INTERFACE", "PYTHON_APP")
    app = setup_app()
    app.run(port=PORT)
