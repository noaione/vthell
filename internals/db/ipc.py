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
__all__ = ("IPCServerClientBridge", "IPCConnection")
logger = logging.getLogger("internals.IPC")


def create_id():
    ctime = pendulum.now("UTC").int_timestamp
    return f"ipc-{rng_string(5)}-{ctime}"


class RemoteDisconnection(Exception):
    def __init__(self, conn: IPCConnection):
        self.conn = conn
        super().__init__(f"Remote connection {conn.id} disconnected")


class IPCConnection:
    def __init__(self, app: SanicVTHell, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._id = create_id()
        self._app: SanicVTHell = app
        self.reader = reader
        self.writer = writer

        self._drain_lock = asyncio.Lock()

        self._msg_receiver: asyncio.Queue[WebSocketPacket] = asyncio.Queue()
        self._msg_sender: asyncio.Queue[WebSocketPacket] = asyncio.Queue()

        self._listener_tasks: Dict[asyncio.Task] = {}
        self._closed = False

    @property
    def id(self):
        return self._id

    def close(self):
        if self._closed:
            return
        if not self.reader.at_eof():
            self.reader.feed_eof()
        self.writer.close()

        for task in self._listener_tasks.values():
            task.cancel()
        self._closed = True

    def _encode_packet(self, packet: WebSocketPacket):
        as_json = packet.to_ws()
        return orjson.dumps(as_json).decode("utf-8")

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

    async def _listen_for_message(self):
        try:
            while True:
                packet = await self._msg_receiver.get()

                if packet.event.startswith("ws_"):
                    logger.debug("Got IPC event from server %s, rebroadcasting to WS emitter", packet.event)
                    event_name = packet.event[3:]
                    await self._app.wshandler.emit(event_name, packet.data)
        except asyncio.CancelledError:
            return

    async def _receiver(self):
        try:
            while True:
                try:
                    data = await self.read_message()
                except RemoteDisconnection:
                    break
                packet = self._decode_message(data)
                if packet is None:
                    continue

                await self._msg_receiver.put(packet)
        except asyncio.CancelledError:
            return

    async def _dispatcher(self):
        try:
            while True:
                packet = await self._msg_sender.get()
                try:
                    await self.send_message(self._encode_packet(packet))
                except RemoteDisconnection:
                    break
        except asyncio.CancelledError:
            return

    async def emit(self, event: str, data: Any):
        packet = WebSocketPacket(event, data)
        await self._msg_sender.put(packet)

    async def send_message(self, message: Union[str, bytes]):
        if isinstance(message, str):
            message = message.encode("utf-8")
        with_eof_bytes = message + b"\x04\x04\x04"

        try:
            logger.debug("Sending IPC message to client: %s", message)
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
            logger.debug("Got IPC message from client: %d bytes", len(raw_data))
            return raw_data.decode("utf-8")
        except (asyncio.IncompleteReadError, BrokenPipeError, ConnectionResetError):
            raise RemoteDisconnection(self)

    def _closed_down_task(self, task: asyncio.Task):
        task_name = task.get_name()
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"Task {task_name} failed with exception: {exception}", exc_info=exception)
        except asyncio.exceptions.InvalidStateError:
            pass
        self._listener_tasks.pop(task_name, None)
        logger.debug(f"Task {task_name} finished")

    async def establish(self):
        sid = self._id
        receive_task = asyncio.ensure_future(self._receiver())
        dispatch_task = asyncio.ensure_future(self._dispatcher())
        if isinstance(receive_task, asyncio.Task):
            receive_task.set_name(f"ipc-client_{sid}-receiver_task")
            receive_task.add_done_callback(self._closed_down_task)
            self._listener_tasks[f"ipc-client_{sid}-receiver_task"] = receive_task
        if isinstance(dispatch_task, asyncio.Task):
            dispatch_task.set_name(f"ipc-client_{sid}-dispatcher_task")
            dispatch_task.add_done_callback(self._closed_down_task)
            self._listener_tasks[f"ipc-client_{sid}-dispatcher_task"] = dispatch_task

        _, pending = await asyncio.wait(
            [receive_task, dispatch_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        logger.info("Stopping all IPC task for %s since it closed down.", sid)
        for task in pending:
            logger.debug("Cancelling %s", task.get_name())
            task.cancel()
        self.close()


class IPCServerClientBridge:
    def __init__(self) -> None:
        self.__ipc_path = BASE_PATH / "dbs" / "sanic-ipc_do_not_delete.sock"
        self._app: Optional[SanicVTHell] = None

        self._connection_manager: Dict[str, IPCConnection] = {}

        self._extra_tasks: Dict[str, asyncio.Task] = {}

    @property
    def ipc_path(self):
        return self.__ipc_path

    async def _wait_until_ready(self):
        while True:
            is_exist = await self._app.loop.run_in_executor(None, self.__ipc_path.exists)
            if is_exist:
                break
            await asyncio.sleep(0.5)

    async def create_server(self):
        server: asyncio.AbstractServer = await asyncio.start_unix_server(
            self._handle_connection, path=str(self.__ipc_path)
        )

        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            server.close()
            await server.wait_closed()

    async def connect_client(self):
        try:
            await self._wait_until_ready()
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            return
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.__ipc_path))
        except FileNotFoundError:
            pass

        conn = IPCConnection(self._app, reader, writer)
        logger.info("Connection established %s, trying to send hi message", conn.id)
        task_name = f"ipc-client-{conn.id}_client_loop_task"
        task = self._app.loop.create_task(conn.establish(), name=task_name)
        task.add_done_callback(self.connection_done_task)
        self._connection_manager[conn.id] = conn

    def connection_done_task(self, task: asyncio.Task):
        task_name = task.get_name()
        # ipc-client-{conn.id}_client_loop_task
        actual_id = task_name.replace("ipc-client-", "")
        actual_id = actual_id.replace("_client_loop_task", "")
        conn = self._connection_manager.pop(actual_id, None)
        if conn is not None:
            logger.info("Connection %s closed", actual_id)
            conn.close()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = IPCConnection(self._app, reader, writer)
        logger.info("New connection %s", conn.id)
        task_name = f"ipc-client-{conn.id}_client_loop_task"
        task = self._app.loop.create_task(conn.establish(), name=task_name)
        task.add_done_callback(self.connection_done_task)
        self._extra_tasks[task_name] = task
        self._connection_manager[conn.id] = conn

    async def emit(self, event: str, data: Any):
        for conn in self._connection_manager.values():
            await conn.emit(event, data)

    def close(self):
        for conn in self._connection_manager.values():
            conn.close()
        for task in self._extra_tasks.values():
            task.cancel()

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
            logger.info(f"IPC worker: {app.worker_num}")
            if app.first_process:
                logger.info("Starting IPC server...")
                task_name = f"ipc-server-startup-{ctime}"
                task_main = app.loop.create_task(self.create_server(), name=task_name)
                task_main.add_done_callback(self._closed_down_task)
            else:
                logger.info("Starting IPC client...")
                task_name = f"ipc-client-startup-{ctime}"
                task_main = app.loop.create_task(self.connect_client(), name=task_name)
                task_main.add_done_callback(self._closed_down_task)

            self._extra_tasks[task_name] = task_main

        app.add_task(_attach_listener, name="ipc-server-client-startup-attacher")
