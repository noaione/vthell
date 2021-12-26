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
import os
from dataclasses import dataclass, field
from glob import glob
from pathlib import Path
from typing import TYPE_CHECKING, Any, AnyStr, Callable, Dict, List, Optional, Tuple, Type, Union

import aiofiles
import orjson
import pendulum
import watchgod as wg
from sanic import Sanic, reloader_helpers
from sanic.config import SANIC_PREFIX, Config
from sanic.server.protocols.http_protocol import HttpProtocol
from sanic.server.protocols.websocket_protocol import WebSocketProtocol

from internals.db import IPCServerClientBridge
from internals.runner import serve_multiple, serve_single
from internals.struct import VTHellRecords
from internals.ws import WebsocketServer

if TYPE_CHECKING:
    from socket import socket
    from ssl import SSLContext

    from sanic.handlers import ErrorHandler
    from sanic.request import Request
    from sanic.router import Router
    from sanic.signals import SignalRouter
    from tortoise.backends.sqlite.client import SqliteClient

    from .holodex import HolodexAPI


__all__ = ("SanicVTHellConfig", "SanicVTHell", "VTHellDataset", "VTHellDatasetVTuber")

logger = logging.getLogger("Internals.VTHell")
CURRENT_PATH = Path(__file__).absolute().parent.parent


def orjson_dumps(obj: Any, default: Callable[[Any], Any] = None, option: Optional[int] = None) -> AnyStr:
    """
    Serialize an object using orjson.
    """

    OPTS_DEFAULT = orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS | orjson.OPT_PASSTHROUGH_DATACLASS
    if option is None:
        option = OPTS_DEFAULT
    else:
        option |= OPTS_DEFAULT

    kwargs = {
        "option": option,
    }
    if default is not None:
        kwargs["default"] = default

    return orjson.dumps(obj, **kwargs)


@dataclass
class VTHellDatasetVTuber:
    name: str
    youtube: Optional[str]
    bilibili: Optional[str]
    twitch: Optional[str]
    twitcasting: Optional[str]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> VTHellDatasetVTuber:
        return cls(
            name=d["name"],
            youtube=d.get("youtube"),
            bilibili=d.get("bilibili"),
            twitch=d.get("twitch"),
            twitcasting=d.get("twitcasting"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "youtube": self.youtube,
            "bilibili": self.bilibili,
            "twitch": self.twitch,
            "twitcasting": self.twitcasting,
        }


@dataclass
class VTHellDataset:
    id: str
    name: str
    main_key: str
    upload_base: str
    vliver: List[VTHellDatasetVTuber]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> VTHellDataset:
        return cls(
            id=d["id"],
            name=d["name"],
            main_key=d["main_key"],
            upload_base=d["upload_base"],
            vliver=[VTHellDatasetVTuber.from_dict(v) for v in d["vliver"]],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "main_key": self.main_key,
            "upload_base": self.upload_base,
            "vliver": [v.to_dict() for v in self.vliver],
        }

    def build_path(self, vtuber: VTHellDatasetVTuber):
        paths = []
        main_target = self.upload_base.replace("\\", "/").split("/")
        paths.extend(main_target)
        if vtuber is None:
            paths.append("Unknown")
        else:
            paths.append(vtuber.name)
        return paths


@dataclass
class VTHellRecordedData:
    data: Optional[VTHellRecords] = None
    last_updated: int = field(default_factory=lambda: pendulum.now("UTC").int_timestamp)
    total_size: int = 0

    def update(self, data: VTHellRecords, size: int):
        self.data = data
        self.last_updated = pendulum.now("UTC").int_timestamp
        self.total_size = size

    def to_json(self) -> Dict[str, Any]:
        actual_data = self.data
        if actual_data is not None:
            actual_data = actual_data.to_json()
        return {
            "data": actual_data,
            "last_updated": self.last_updated,
            "total_size": self.total_size,
        }


class SanicVTHellConfig(Config):
    VTHELL_DB: str
    VTHELL_LOOP_DOWNLOADER: int
    VTHELL_LOOP_SCHEDULER: int
    VTHELL_GRACE_PERIOD: int

    HOLODEX_API_KEY: str

    RCLONE_PATH: str
    RCLONE_DISABLE: bool
    RCLONE_DRIVE_TARGET: str
    YTARCHIVE_PATH: str
    MKVMERGE_PATH: str
    FFMPEG_PATH: str

    WEBSERVER_REVERSE_PROXY: bool
    WEBSERVER_REVERSE_PROXY_SECRET: str
    WEBSERVER_PASSWORD: str

    NOTIFICATION_DISCORD_WEBHOOK: str


class SanicVTHell(Sanic):
    db: SqliteClient
    config: SanicVTHellConfig
    holodex: HolodexAPI
    vtdataset: Dict[str, VTHellDataset]
    vtrecords: VTHellRecordedData
    wshandler: WebsocketServer
    ipc: IPCServerClientBridge
    worker_num: int

    def __init__(
        self,
        name: str = None,
        config: Optional[SanicVTHellConfig] = None,
        ctx: Optional[Any] = None,
        router: Optional[Router] = None,
        signal_router: Optional[SignalRouter] = None,
        error_handler: Optional[ErrorHandler] = None,
        load_env: Union[bool, str] = True,
        env_prefix: Optional[str] = SANIC_PREFIX,
        request_class: Optional[Type[Request]] = None,
        strict_slashes: bool = False,
        log_config: Optional[Dict[str, Any]] = None,
        configure_logging: bool = True,
        register: Optional[bool] = None,
        dumps: Optional[Callable[..., AnyStr]] = orjson_dumps,
    ) -> None:
        super().__init__(
            name=name,
            config=config,
            ctx=ctx,
            router=router,
            signal_router=signal_router,
            error_handler=error_handler,
            load_env=load_env,
            env_prefix=env_prefix,
            request_class=request_class,
            strict_slashes=strict_slashes,
            log_config=log_config,
            configure_logging=configure_logging,
            register=register,
            dumps=dumps,
        )

        self.holodex: HolodexAPI = None
        self.db: SqliteClient = None
        self.vtrecords = VTHellRecordedData()

        try:
            db_path = self.config["VTHELL_DB"]
            if not db_path.endswith(".db"):
                db_path += ".db"
            self.config["VTHELL_DB"] = db_path
        except KeyError:
            self.config["VTHELL_DB"] = "vth.db"

        try:
            check = self.config["VTHELL_LOOP_DOWNLOADER"]
            if not isinstance(check, (int, float)):
                try:
                    check = float(check)
                except ValueError:
                    check = 60
                    logger.error("VTHELL_LOOP_DOWNLOADER must be a number, not %s (fallback to 60s)", check)
            self.config["VTHELL_LOOP_DOWNLOADER"] = check
        except KeyError:
            # Default to check every 1 minute
            self.config["VTHELL_LOOP_DOWNLOADER"] = 60

        try:
            check = self.config["VTHELL_LOOP_SCHEDULER"]
            if not isinstance(check, (int, float)):
                try:
                    check = float(check)
                except ValueError:
                    check = 180
                    logger.error("VTHELL_LOOP_SCHEDULER must be a number, not %s (fallback to 180s)", check)
            self.config["VTHELL_LOOP_SCHEDULER"] = check
        except KeyError:
            # Default to check every 3 minutes
            self.config["VTHELL_LOOP_SCHEDULER"] = 180

        try:
            check = self.config["VTHELL_GRACE_PERIOD"]
            if not isinstance(check, (int, float)):
                try:
                    check = float(check)
                except ValueError:
                    check = 120
                    logger.error("VTHELL_GRACE_PERIOD must be a number, not %s (fallback to 120s)", check)
            self.config["VTHELL_GRACE_PERIOD"] = check
        except KeyError:
            # Default to start waiting 2 minutes before scheduled start
            self.config["VTHELL_GRACE_PERIOD"] = 120

        if self.config.get("WEBSERVER_REVERSE_PROXY", False):
            secret_reverse = self.config.get("WEBSERVER_REVERSE_PROXY_SECRET", "").strip()
            if secret_reverse == "":
                logger.error("WEBSERVER_REVERSE_PROXY_SECRET is empty while reverse proxy is enabled")
                raise RuntimeError("WEBSERVER_REVERSE_PROXY_SECRET is empty while reverse proxy is enabled")

            self.config.FORWARDED_SECRET = secret_reverse

        if self.config.get("WEBSERVER_PASSWORD", "").strip() == "":
            logger.error("WEBSERVER_PASSWORD is empty")
            raise RuntimeError("WEBSERVER_PASSWORD is empty")

        self.startup_vthell_dataset()
        self.wshandler = WebsocketServer(self)
        self.wshandler.attach()

        self.ipc = None
        self.worker_num = 0

    @property
    def first_process(self):
        worker_num = getattr(self, "worker_num", 0)
        return worker_num == 0

    async def wait_until_ready(self) -> None:
        """
        Block until all the asyncio tasks are ready
        """
        if not hasattr(self, "_db_ready"):
            self._db_ready = asyncio.Event()
        if not hasattr(self, "_holodex_ready"):
            self._holodex_ready = asyncio.Event()
        if not hasattr(self, "_wshandler_ready"):
            self._wshandler_ready = asyncio.Event()
        await self._db_ready.wait()
        await self._holodex_ready.wait()
        await self._wshandler_ready.wait()

    def mark_db_ready(self):
        if not hasattr(self, "_db_ready"):
            self._db_ready = asyncio.Event()
        self._db_ready.set()

    def mark_holodex_ready(self):
        if not hasattr(self, "_holodex_ready"):
            self._holodex_ready = asyncio.Event()
        self._holodex_ready.set()

    def mark_wshandler_ready(self):
        if not hasattr(self, "_wshandler_ready"):
            self._wshandler_ready = asyncio.Event()
        self._wshandler_ready.set()

    def startup_vthell_dataset(self):
        self.vtdataset = {}
        dataset_path = CURRENT_PATH / "dataset"
        globbed_dataset = glob(str(dataset_path / "*.json"))
        logger.info("Found %d dataset(s)", len(globbed_dataset))
        for dataset in globbed_dataset:
            if dataset.startswith("_"):
                continue
            with open(dataset, "r") as f:
                dataset_str = f.read()

            path_fn, _ = os.path.splitext(Path(dataset).name)

            as_json = orjson.loads(dataset_str)
            try:
                data = VTHellDataset.from_dict(as_json)
                self.vtdataset[path_fn] = data
            except Exception as exc:
                logger.error("Invalid dataset file %s", dataset, exc_info=exc)

        logger.info("Loaded %d dataset", len(self.vtdataset))
        self.add_task(self.watch_vthell_dataset_folder)

    def find_id_on_dataset(
        self, id: str, platform: str
    ) -> Optional[Tuple[VTHellDataset, VTHellDatasetVTuber]]:
        for dataset in self.vtdataset.values():
            for v in dataset.vliver:
                if getattr(v, platform, None) == id:
                    return dataset, v
        return None, None

    def create_rclone_path(self, id: str, platform: str) -> List[str]:
        dataset, vtuber = self.find_id_on_dataset(id, platform)
        if not dataset:
            return ["Unknown"]
        return dataset.build_path(vtuber)

    def run(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        *,
        debug: bool = False,
        auto_reload: Optional[bool] = None,
        ssl: Union[Dict[str, str], SSLContext, None] = None,
        sock: Optional[socket] = None,
        workers: int = 1,
        protocol: Optional[Type[asyncio.Protocol]] = None,
        backlog: int = 100,
        register_sys_signals: bool = True,
        access_log: Optional[bool] = None,
        unix: Optional[str] = None,
        loop: None = None,
        reload_dir: Optional[Union[List[str], str]] = None,
    ) -> None:
        if reload_dir:
            if isinstance(reload_dir, str):
                reload_dir = [reload_dir]

            for directory in reload_dir:
                direc = Path(directory)
                if not direc.is_dir():
                    logger.warning(f"Directory {directory} could not be located")
                self.reload_dirs.add(Path(directory))

        if loop is not None:
            raise TypeError(
                "loop is not a valid argument. To use an existing loop, "
                "change to create_server().\nSee more: "
                "https://sanic.readthedocs.io/en/latest/sanic/deploying.html"
                "#asynchronous-support"
            )

        if auto_reload or auto_reload is None and debug:
            self.auto_reload = True
            if os.environ.get("SANIC_SERVER_RUNNING") != "true":
                return reloader_helpers.watchdog(1.0, self)

        if sock is None:
            host, port = host or "127.0.0.1", port or 8000

        if protocol is None:
            protocol = WebSocketProtocol if self.websocket_enabled else HttpProtocol
        # if access_log is passed explicitly change config.ACCESS_LOG
        if access_log is not None:
            self.config.ACCESS_LOG = access_log

        server_settings = self._helper(
            host=host,
            port=port,
            debug=debug,
            ssl=ssl,
            sock=sock,
            unix=unix,
            workers=workers,
            protocol=protocol,
            backlog=backlog,
            register_sys_signals=register_sys_signals,
            auto_reload=auto_reload,
        )

        try:
            self.is_running = True
            self.is_stopping = False
            if workers > 1 and os.name != "posix":
                logger.warn(
                    f"Multiprocessing is currently not supported on {os.name}," " using workers=1 instead"
                )
                workers = 1
            if workers == 1:
                serve_single(server_settings)
            else:
                serve_multiple(server_settings, workers)
        except BaseException:
            logger.exception("Experienced exception while trying to serve")
            raise
        finally:
            self.is_running = False
        logger.info("Server Stopped")

    async def watch_vthell_dataset_folder(self, app: SanicVTHell):
        if app.first_process:
            return
        dataset_path = CURRENT_PATH / "dataset"
        logger.info("Watching dataset folder %s", dataset_path)
        async for changes in wg.awatch(
            str(dataset_path), watcher_cls=wg.RegExpWatcher, watcher_kwargs=dict(re_files=r"^.*(\.json)$")
        ):
            for change in changes:
                action, path = change
                path_f = Path(path)
                path_fn, _ = os.path.splitext(path_f.name)
                if path_fn.startswith("_"):
                    continue
                if action == wg.Change.deleted:
                    logger.info("[dataset-watch] Dataset %s got deleted, removing", path_fn)
                    self.vtdataset.pop(path_fn, None)
                else:
                    async with aiofiles.open(path, "r") as f:
                        dataset_str = await f.read()

                    as_json = orjson.loads(dataset_str)
                    try:
                        data = VTHellDataset.from_dict(as_json)
                        logger.info("[dataset-watch] Reloading dataset %s", path_fn)
                        self.vtdataset[path_fn] = data
                    except Exception as exc:
                        logger.error("[dataset-watch] Invalid dataset file %s", path, exc_info=exc)
