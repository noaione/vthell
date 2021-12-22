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

A custom IPC server/client to communicate inbetween database process
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import orjson
import pendulum

from internals.utils import rng_string
from internals.ws import WebSocketPacket

if TYPE_CHECKING:
    from internals.vth import SanicVTHell


BASE_PATH = Path(__file__).absolute().parent.parent.parent
__all__ = ("IPCClient", "IPCServer")
logger = logging.getLogger("internals.IPC")


def create_id():
    ctime = pendulum.now("UTC").int_timestamp
    return f"ipc-{rng_string(5)}-{ctime}"


class RemoteDisconnection(Exception):
    def __init__(self, conn: IPCConnection):
        self.conn = conn
        super().__init__(f"Remote connection {conn.id} disconnected")


class IPCConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._id = create_id()
        self.reader = reader
        self.writer = writer

        self._drain_lock = asyncio.Lock()

    @property
    def id(self):
        return self._id

    def close(self):
        if not self.reader.at_eof():
            self.reader.feed_eof()
        self.writer.close()

    async def send_message(self, message: Union[str, bytes]):
        if isinstance(message, str):
            message = message.encode("utf-8")
        with_eof_bytes = message + b"\x04\x04\x04"

        try:
            self.writer.write(with_eof_bytes)
            async with self._drain_lock:
                await self.writer.drain()
        except (BrokenPipeError, ConnectionResetError):
            raise RemoteDisconnection(self)
        except RuntimeError as err:
            if "handler is closed" in str(err).lower():
                logger.debug("Failed to send %s. Handler closed", message)
                raise RemoteDisconnection(self) from err
            raise

    async def read_message(self):
        if self.reader.at_eof():
            raise RemoteDisconnection(self)

        try:
            raw_data = await self.reader.readuntil(b"\x04\x04\x04")
            if raw_data.endswith(b"\x04\x04\x04"):
                raw_data = raw_data[:-3]
            return raw_data.decode("utf-8")
        except (asyncio.IncompleteReadError, BrokenPipeError, ConnectionResetError):
            raise RemoteDisconnection(self)


class IPCServer:
    def __init__(self) -> None:
        self.__ipc_path = BASE_PATH / "dbs" / "sanic-ipc_do_not_delete.sock"
        self._app: Optional[SanicVTHell] = None

        self._connection_manager: Dict[str, IPCConnection] = {}
        self._msg_queue: asyncio.Queue[WebSocketPacket] = None

        self._extra_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self):
        server: asyncio.AbstractServer = await asyncio.start_unix_server(
            self._handle_connection, path=str(self.__ipc_path)
        )

        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            server.close()
            await server.wait_closed()

    def close(self):
        self._disonnect_all()
        for task in self._extra_tasks.values():
            task.cancel()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = IPCConnection(reader, writer)
        await conn.send_message("hello")
        response = await conn.read_message()
        if response == "hi":
            logger.info("New connection %s", conn.id)
            self._connection_manager[conn.id] = conn
        else:
            logger.warning("Unexpected response from %s: %s", conn.id, response)
            conn.close()

    def _encode_packet(self, packet: WebSocketPacket):
        as_json = packet.to_ws()
        return orjson.dumps(as_json).decode("utf-8")

    async def emit(self, event: str, data: Any):
        packet = WebSocketPacket(event, data)
        await self._msg_queue.put(packet)

    def _disconnect(self, conn: IPCConnection):
        conn.close()
        self._connection_manager.pop(conn.id, None)

    def _disonnect_all(self):
        copy_data = self._connection_manager.copy()
        for conn in copy_data.values():
            self._disconnect(conn)

    async def _quick_dispatcher(self):
        try:
            while True:
                packet = await self._msg_queue.get()
                for conn in list(self._connection_manager.values())[:]:
                    try:
                        await conn.send_message(self._encode_packet(packet))
                    except RemoteDisconnection:
                        self._disconnect(conn)
        except asyncio.CancelledError:
            self._disonnect_all()

    def _closed_down_task(self, task: asyncio.Task):
        task_name = task.get_name()
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"Task {task_name} failed with exception: {exception}", exc_info=exception)
        except asyncio.exceptions.InvalidStateError:
            pass
        self._extra_tasks.pop(task_name, None)
        logger.debug(f"Task {task_name} finished")

    def attach(self, app: SanicVTHell):
        self._app = app

        async def _attach_listener(app: SanicVTHell):
            ctime = pendulum.now("UTC").int_timestamp
            self._msg_queue = asyncio.Queue()
            fnmae = f"ipc-server-{ctime}"
            logger.info("Starting IPC server dispatcher %s", fnmae)
            task_dispatch = app.loop.create_task(self._quick_dispatcher(), name=fnmae + "-dispatcher")
            task_dispatch.add_done_callback(self._closed_down_task)
            self._extra_tasks[fnmae + "-dispatcher"] = task_dispatch
            logger.info("Starting IPC server...")
            task_main = app.loop.create_task(self.connect(), name=fnmae)
            task_main.add_done_callback(self._closed_down_task)
            self._extra_tasks[fnmae] = task_main

        app.add_task(_attach_listener)


class IPCClient:
    def __init__(self) -> None:
        self.__ipc_path = BASE_PATH / "dbs" / "sanic-ipc_do_not_delete.sock"
        self._app: Optional[SanicVTHell] = None

        self._conn: IPCConnection = None
        self._conn_ready = asyncio.Event()
        self._msg_queue: asyncio.Queue[WebSocketPacket] = None

        self._extra_tasks: Dict[str, asyncio.Task] = {}

    async def _wait_until_ready(self):
        while True:
            is_exist = await self._app.loop.run_in_executor(None, self.__ipc_path.exists)
            if is_exist:
                break
            await asyncio.sleep(0.5)

    def close(self):
        if self._conn:
            self._conn.close()

        for task in self._extra_tasks.values():
            task.cancel()

    async def connect(self):
        try:
            await self._wait_until_ready()
        except asyncio.CancelledError:
            return
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.__ipc_path))
        except FileNotFoundError:
            pass

        conn = IPCConnection(reader, writer)
        response = await conn.read_message()
        if response == "hello":
            logger.info("Connection established %s, trying to send hi message", conn.id)
            await conn.send_message("hi")
            self._conn = conn
            self._conn_ready.set()
        else:
            logger.warning("Unexpected init from %s: %s", conn.id, response)
            conn.close()

    def _decode_message(self, message: str):
        if not message:
            return None
        try:
            as_json = orjson.loads(message)
        except Exception:
            return None
        try:
            return WebSocketPacket.from_ws(as_json)
        except (ValueError, TypeError):
            return None

    async def _message_receiver(self):
        await self._conn_ready.wait()
        while True:
            data = await self._conn.read_message()
            packet = self._decode_message(data)
            if packet is None:
                continue

            await self._msg_queue.put(packet)

    async def _listen_for_message(self):
        while True:
            data = await self._msg_queue.get()
            print(data)

    def _closed_down_task(self, task: asyncio.Task):
        task_name = task.get_name()
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"Task {task_name} failed with exception: {exception}", exc_info=exception)
        except asyncio.exceptions.InvalidStateError:
            pass
        self._extra_tasks.pop(task_name, None)
        logger.debug(f"Task {task_name} finished")

    def attach(self, app: SanicVTHell):
        self._app = app

        async def _attach_listener(app: SanicVTHell):
            ctime = pendulum.now("UTC").int_timestamp
            self._msg_queue = asyncio.Queue()
            fnmae = f"ipc-server-{ctime}"
            logger.info("Starting IPC server listener %s", fnmae)
            task_dispatch = app.loop.create_task(self._listen_for_message(), name=fnmae + "-listener")
            task_dispatch.add_done_callback(self._closed_down_task)
            self._extra_tasks[fnmae + "-listener"] = task_dispatch
            logger.info("Starting IPC client...")
            await self.connect()
            task_main = app.loop.create_task(self._message_receiver(), name=fnmae)
            task_main.add_done_callback(self._closed_down_task)
            self._extra_tasks[fnmae] = task_main

        app.add_task(_attach_listener)
