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
import os
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import TYPE_CHECKING, Any, AnyStr, Callable, Dict, List, Optional, Tuple, Type, Union

import aiofiles
import orjson
import watchgod as wg
from sanic import Sanic
from sanic.config import SANIC_PREFIX, Config

if TYPE_CHECKING:
    import socketio
    from sanic.handlers import ErrorHandler
    from sanic.request import Request
    from sanic.router import Router
    from sanic.signals import SignalRouter
    from tortoise.backends.sqlite.client import SqliteClient

    from .holodex import HolodexAPI


__all__ = ("SanicVTHellConfig", "SanicVTHell", "VTHellDataset", "VTHellDatasetVTuber")

logger = logging.getLogger("internals.vth")
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


class SanicVTHellConfig(Config):
    VTHELL_DB: str
    VTHELL_LOOP_DOWNLOADER: int
    VTHELL_LOOP_SCHEDULER: int
    VTHELL_GRACE_PERIOD: int

    HOLODEX_API_KEY: str

    RCLONE_PATH: str
    RCLONE_DRIVE_TARGET: str
    YTARCHIVE_PATH: str
    MKVMERGE_PATH: str

    WEBSERVER_REVERSE_PROXY: bool
    WEBSERVER_REVERSE_PROXY_SECRET: str
    WEBSERVER_PASSWORD: str


class SanicVTHell(Sanic):
    db: SqliteClient
    config: SanicVTHellConfig
    holodex: HolodexAPI
    sio: socketio.AsyncServer
    vtdataset: Dict[str, VTHellDataset]

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

        self.sio: socketio.AsyncServer = None
        self.holodex: HolodexAPI = None

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
            self.config["VTHELL_GRACE_PERIOD"]
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

    async def watch_vthell_dataset_folder(self, app: SanicVTHell):
        dataset_path = CURRENT_PATH / "dataset"
        logger.info("Watching dataset folder %s", dataset_path)
        async for changes in wg.awatch(
            str(dataset_path), watcher_cls=wg.RegExpWatcher, watcher_kwargs=dict(re_files=r"^.*(\.json)$")
        ):
            for change in changes:
                action, path = change
                path_f = Path(path)
                path_fn, _ = os.path.splitext(path_f.name)
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
