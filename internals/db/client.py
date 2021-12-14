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
from os.path import realpath
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Dict, Iterable, Optional

from tortoise import Tortoise

if TYPE_CHECKING:
    from internals.vth import SanicVTHell


logger = logging.getLogger("internals.db")
DB_PATH = Path(__file__).absolute().parent.parent.parent / "dbs"

__all__ = ("register_db",)


def register_db(
    app: SanicVTHell,
    config: Optional[dict] = None,
    config_file: Optional[str] = None,
    modules: Optional[Dict[str, Iterable[str, ModuleType]]] = None,
    generate_schemas: bool = False,
):
    @app.listener("before_server_start")
    async def init_orm(app: SanicVTHell, loop: asyncio.AbstractEventLoop):
        db_name = app.config["VTHELL_DB"]
        db_path = realpath(DB_PATH / db_name)
        await Tortoise.init(
            config=config,
            config_file=config_file,
            db_url=f"sqlite://{db_path}",
            modules=modules,
        )
        logger.info("Tortoise-ORM started: %s, %s", Tortoise._connections, Tortoise.apps)
        connection = list(Tortoise._connections.values())[0]
        app.db = connection
        if generate_schemas:
            logger.info("Generating schemas")
            await Tortoise.generate_schemas()

    @app.listener("after_server_stop")
    async def close_orm(app: SanicVTHell, loop: asyncio.AbstractEventLoop):
        logger.info("Closing Tortoise-ORM")
        await Tortoise.close_connections()
        logger.info("Tortoise-ORM closed")
