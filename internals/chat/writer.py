import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import orjson

if TYPE_CHECKING:
    from aiofiles.threadpool.binary import AsyncBufferedReader

SAVE_PATH = Path(__file__).absolute().parent.parent.parent / "chatarchive"


class JSONWriter:
    def __init__(self, file_name: str, overwrite: bool = True) -> None:
        if not file_name.endswith(".json"):
            file_name += ".json"
        self.filename = file_name
        self.save_path = SAVE_PATH / file_name
        self.overwrite = overwrite
        self.file: AsyncBufferedReader = None
        self._is_closed: bool = True

    @property
    def closed(self):
        return self._is_closed

    async def init(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.save_path.parent.mkdir, 0o777, True, True)
        await loop.run_in_executor(None, self.save_path.touch)
        previous_items = []
        file = await aiofiles.open(str(self.save_path), "rb+")
        self.file = file
        self._is_closed = False
        if not self.overwrite:
            load_data = await file.read()
            try:
                previous_items = orjson.loads(load_data)
            except orjson.JSONDecodeError:
                pass

        await file.truncate(0)
        for previous in previous_items:
            await self.write(previous)

    def _multiline_indent(self, text):
        padding = 2 * " "
        return "".join(map(lambda x: padding + x, text.splitlines(True)))

    async def close(self):
        if self.file and not self.closed:
            await self.file.close()

    async def flush(self):
        await self.file.flush()

    async def _actual_write(self, item: Any, flush: bool = False):
        await self.file.seek(0, os.SEEK_END)

        to_write = orjson.dumps(item, option=orjson.OPT_INDENT_2).decode("utf-8")
        to_write = "\n" + self._multiline_indent(to_write)

        if await self.file.tell() == 0:
            await self.file.write("[".encode("utf-8"))
        else:
            await self.file.seek(-2, os.SEEK_END)
            await self.file.write(", ".encode("utf-8"))

        await self.file.write(to_write.encode("utf-8"))
        await self.file.write("\n]".encode("utf-8"))

        if flush:
            await self.flush()

    async def write(self, item: Any, flush: bool = False):
        # Safe guard against cancel flags from asyncio
        try:
            await self._actual_write(item, flush)
        except asyncio.CancelledError:
            await self.close()
