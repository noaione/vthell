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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

import orjson
import pendulum
from sanic.server.websockets.connection import WebSocketConnection
from sanic.server.websockets.impl import WebsocketImplProtocol
from websockets.exceptions import ConnectionClosed

from internals.utils import rng_string

from .models import WebSocketMessage, WebSocketPacket

WebsocketProto = Union[WebsocketImplProtocol, WebSocketConnection]

if TYPE_CHECKING:

    from internals.vth import SanicVTHell

    NormalDataCallback = Callable[[Optional[Any]], None]
    SpecialDataCallback = Callable[[str, Optional[WebsocketProto]], None]
    DataCallback = Union[NormalDataCallback, SpecialDataCallback]


logger = logging.getLogger("Internals.WSServer")

__all__ = ("WebsocketServer",)


@dataclass
class WebsocketClient:
    ws: WebsocketProto = field(repr=False, hash=False)
    terminated: asyncio.Event = None

    def __post_init__(self):
        self.terminated = asyncio.Event()

    def terminate(self):
        self.terminated.set()

    async def poll(self):
        await self.terminated.wait()


class PongTimeoutException(Exception):
    """So we can trigger it and make the connection stop"""

    pass


# Based on: https://stackoverflow.com/a/57483591
class WebsocketServer:
    SPECIAL_EVENTS = ["connect", "disconnect"]
    PING_TIMEOUT = 30

    def __init__(self, app: SanicVTHell):
        self.app = app
        self._clients: Dict[str, WebsocketClient] = {}
        self._listener_callbacks: Dict[str, List[DataCallback]] = {}

        self._listener_queue: asyncio.Queue[WebSocketMessage] = asyncio.Queue()
        self._dispatch_queue: asyncio.Queue[WebSocketPacket] = asyncio.Queue()

        self._dispatch_task: asyncio.Task = None
        self._listener_task: asyncio.Task = None

        self._running_tasks: Dict[str, asyncio.Task] = {}
        self.on("pong", self._pong)

    def create_id(self):
        ctime = pendulum.now("UTC").int_timestamp
        return f"{rng_string(5)}-{ctime}"

    def close(self):
        self._clients.clear()
        self._listener_callbacks.clear()
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
        if self._listener_task is not None:
            self._listener_task.cancel()
        for task in self._running_tasks.values():
            task.cancel()

    def _encode_packet(self, packet: WebSocketPacket):
        as_json = packet.to_ws()
        return orjson.dumps(as_json).decode("utf-8")

    def _decode_packet(self, packet: Any):
        if packet is None:
            logger.debug("Received null packet from client, dropping")
            return
        try:
            as_json = orjson.loads(packet)
            try:
                return WebSocketPacket.from_ws(as_json)
            except Exception as e:
                logger.debug("Failed to decode packet", exc_info=e)
        except ValueError:
            logger.debug("Could not decode packet as JSON, dropping")

    async def _scheduled_message_event_consume(
        self, message: WebSocketMessage, listener: DataCallback, special: bool = False
    ):
        if special:
            try:
                await listener(message.sid, self._clients.get(message.sid, None))
            except Exception as e:
                logger.error("Error while handling special event", exc_info=e)
        else:
            try:
                await listener(message.packet.data)
            except PongTimeoutException:
                sid = message.sid
                ws = self._clients.get(sid)
                if ws is not None:
                    ws.terminate()
            except Exception as e:
                logger.error("Error while handling event", exc_info=e)

    async def _internal_listener_task(self):
        try:
            while True:
                recv_message = await self._listener_queue.get()
                ctime = pendulum.now("UTC").int_timestamp
                task_name = f"{recv_message.sid}-{recv_message.packet.event}-{ctime}"
                special_task = recv_message.packet.event in self.SPECIAL_EVENTS
                callback_tasks = self._listener_callbacks.get(recv_message.packet.event, [])
                for i, cb in enumerate(callback_tasks):
                    task = self.app.loop.create_task(
                        self._scheduled_message_event_consume(recv_message, cb, special_task),
                        name=task_name + f"-{i}",
                    )
                    task.add_done_callback(self._closed_down_task)
                    self._running_tasks[task_name + f"-{i}"] = task
                if len(callback_tasks) < 1 and not special_task:
                    logger.warning(f"Unknown event received: {recv_message.packet.event}")
        except asyncio.CancelledError:
            logger.warning("Websocket connection closed")
        except Exception as e:
            logger.debug("Error while listening", exc_info=e)

    async def _scheduled_message_dispatch(self, sid: str, packet: WebSocketPacket):
        try:
            ws = self._clients.get(sid)
            if ws is None:
                logger.warning(f"Client {sid} not found, dropping message")
                return
            if ws.ws is None:
                logger.warning(f"Client {sid} not connected, dropping message")
                return
            await ws.ws.send(self._encode_packet(packet))
        except ConnectionClosed:
            logger.error("Connection closed, removing client %s", sid)
            await self._client_disconnected(sid)
        except Exception as e:
            logger.debug("Error while dispatching", exc_info=e)

    async def _internal_dispatcher_task(self):
        try:
            while True:
                message = await self._dispatch_queue.get()
                ctime = pendulum.now("UTC").int_timestamp
                if message.to is None:
                    for sid in self._clients.copy().keys():
                        task_name = f"{message.event}-{ctime}-{sid}"
                        task = self.app.loop.create_task(
                            self._scheduled_message_dispatch(sid, message),
                            name=task_name,
                        )
                        task.add_done_callback(self._closed_down_task)
                        self._running_tasks[task.get_name()] = task
                else:
                    client = self._clients.get(message.to)
                    if client is None:
                        logger.warning(f"Client {message.to} not found, dropping message")
                        continue
                    task_name = f"{message.event}-{ctime}-{message.to}"
                    task = self.app.loop.create_task(
                        self._scheduled_message_dispatch(message.to, message),
                        name=task_name,
                    )
                    task.add_done_callback(self._closed_down_task)
                    self._running_tasks[task.get_name()] = task
        except asyncio.CancelledError:
            logger.warning("Websocket connection closed")
        except Exception as e:
            logger.debug("Error while dispatching", exc_info=e)

    async def _client_connected(self, ws: WebSocketConnection):
        sid = self.create_id()
        client = WebsocketClient(ws)
        self._clients[sid] = client
        logger.info(f"Client {sid} connected")
        packet = WebSocketPacket(event="connect", data=None)
        message = WebSocketMessage(sid, packet, ws)
        await self._listener_queue.put(message)
        return sid, client

    async def _client_disconnected(self, sid: str, keep_alive_fail: bool = False):
        ws = self._clients.pop(sid, None)
        if ws is None:
            return
        logger.info(f"Client {sid} disconnected")
        if isinstance(ws, WebsocketImplProtocol):
            try:
                logger.debug("Closing websocket connection")
                await ws.close(1006 if keep_alive_fail else 1000)
                logger.debug("Closed connection")
            except Exception as e:
                logger.debug("Error while closing connection", exc_info=e)
        packet = WebSocketPacket(event="disconnect", data=None)
        message = WebSocketMessage(sid, packet, ws)
        await self._listener_queue.put(message)

    async def _pong(self, data: Any):
        if not isinstance(data, dict):
            logger.warning("Invalid pong packet received, dropping")
            return
        t = data.get("t")
        if t is None:
            logger.warning("Empty t data on pong packet, dropping")
            return
        sid = data.get("sid")
        if sid is None:
            logger.warning("Empty sid data on pong packet, dropping")
            return
        distance = int(round(pendulum.now("UTC").float_timestamp * 1000)) - t
        if distance > self.PING_TIMEOUT:
            logger.warning("Pong packet has timed out, closing connection")
            raise PongTimeoutException
        logger.debug("Pong packet received after %d milisecond(s)", distance)

    async def keep_alive(self, sid: str, ws: WebsocketProto):
        try:
            logger.info(f"Starting keep alive handler for {sid}")
            while True:
                try:
                    ping_data = {
                        "t": int(round(pendulum.now("UTC").float_timestamp * 1000)),
                        "sid": sid,
                    }
                    ping_fut = ws.send(self._encode_packet(WebSocketPacket("ping", ping_data)))
                    await asyncio.wait_for(ping_fut, timeout=20)
                except asyncio.TimeoutError:
                    logger.info(
                        "Server failed to sent ping request to %s after 20s, servering connection!", sid
                    )
                    await self._client_disconnected(sid, True)
                    break
                except ConnectionClosed:
                    logger.error("Connection closed, removing client %s", sid)
                    await self._client_disconnected(sid, True)
                    break
                await asyncio.sleep(20)
        except asyncio.CancelledError:
            logger.warning("Receive cancel code from asyncio, stopping...")
        except ConnectionClosed:
            logger.warning("Connection closed, removing client %s", sid)
            await self._client_disconnected(sid, True)
        except Exception as e:
            logger.error("An error occured while trying to process for client %s", sid, exc_info=e)
            await self._client_disconnected(sid, True)

    async def receive_message(self, sid: str, ws: WebsocketProto):
        try:
            logger.info(f"Starting message receiver handler for {sid}")
            while True:
                try:
                    message = await ws.recv()
                    logger.debug(f"Received message from {sid}: {message}")
                    if message is None:
                        # Assume client disconnected.
                        await self._client_disconnected(sid)
                        break
                    parsed_message = self._decode_packet(message)
                    if parsed_message is None:
                        continue
                    await self._listener_queue.put(WebSocketMessage(sid, parsed_message, ws))
                except ConnectionClosed:
                    logger.warning("Connection closed, removing client %s", sid)
                    await self._client_disconnected(sid)
                    break
        except asyncio.CancelledError:
            logger.warning("Receive cancel code from asyncio, stopping...")
        except ConnectionClosed:
            logger.warning("Connection closed, removing client %s", sid)
            await self._client_disconnected(sid)
        except Exception as e:
            logger.error("An error occured while trying to process for client %s", sid, exc_info=e)
            await self._client_disconnected(sid)

    async def error_termination(self, sid: str, ws: WebsocketProto):
        try:
            logger.info(f"Started long polling {sid} for error termination")
            await ws.poll()
            logger.info("Client %s disconnected", sid)
            await self._client_disconnected(sid)
        except asyncio.CancelledError:
            logger.warning("Receive cancel code from asyncio, stopping...")
            await self._client_disconnected(sid)
        except ConnectionClosed:
            logger.warning("Connection closed, removing client %s", sid)
            await self._client_disconnected(sid)
        except PongTimeoutException:
            logger.warning("Pong timeout, closing connection")
            await self._client_disconnected(sid)
        except Exception as e:
            logger.error("An error occured while trying to process for client %s", sid, exc_info=e)
            await self._client_disconnected(sid)

    async def listen(self, ws: WebsocketProto):
        """Start listening for messages from the websocket connection"""
        sid, client = await self._client_connected(ws)

        keep_alive_task = asyncio.ensure_future(self.keep_alive(sid, ws), loop=self.app.loop)
        receive_task = asyncio.ensure_future(self.receive_message(sid, ws), loop=self.app.loop)
        error_poll_task = asyncio.ensure_future(self.error_termination(sid, client), loop=self.app.loop)
        if isinstance(keep_alive_task, asyncio.Task):
            keep_alive_task.set_name(f"ws_client_{sid}-keep-alive")
            keep_alive_task.add_done_callback(self._closed_down_task)
            self._running_tasks[f"ws_client_{sid}-keep-alive"] = keep_alive_task
        if isinstance(receive_task, asyncio.Task):
            receive_task.set_name(f"ws_client_{sid}-receive")
            receive_task.add_done_callback(self._closed_down_task)
            self._running_tasks[f"ws_client_{sid}-receive"] = receive_task
        if isinstance(error_poll_task, asyncio.Task):
            error_poll_task.set_name(f"ws_client_{sid}-error-poll")
            error_poll_task.add_done_callback(self._closed_down_task)
            self._running_tasks[f"ws_client_{sid}-error-poll"] = error_poll_task
        _, pending = await asyncio.wait(
            [keep_alive_task, receive_task, error_poll_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        logger.info("Stopping all ws task for %s since it closed down.", sid)
        for task in pending:
            logger.debug("Cancelling task %s", task.get_name())
            task.cancel()

    def _closed_down_task(self, task: asyncio.Task):
        task_name = task.get_name()
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"Task {task_name} failed with exception: {exception}", exc_info=exception)
        except asyncio.exceptions.InvalidStateError:
            pass
        self._running_tasks.pop(task_name, None)
        logger.debug(f"Task {task_name} finished")

    def attach(self):
        """Attach the websocket server to the application"""

        async def _internal_attacher(app: SanicVTHell):
            ctime = pendulum.now("UTC").int_timestamp
            loop = app.loop
            task_name = f"WebsocketServer-{ctime}"
            logger.info(f"Starting websocket server on task {task_name}")
            # Recreate the Queue since it's running on different loop on init
            self._listener_queue = asyncio.Queue()
            self._dispatch_queue = asyncio.Queue()
            task_listen = loop.create_task(self._internal_listener_task(), name=task_name + "-listen")
            task_listen.add_done_callback(self._closed_down_task)
            task_dispatch = loop.create_task(self._internal_dispatcher_task(), name=task_name + "-dispatch")
            task_dispatch.add_done_callback(self._closed_down_task)
            logger.info("Attaching task into main class...")
            self._dispatch_task = task_dispatch
            self._listener_task = task_listen
            app.mark_wshandler_ready()
            app.wshandler = self
            logger.info("Websocket server attached and ready")

        self.app.add_task(_internal_attacher)

    async def emit(self, event: str, data: Optional[Any] = None, to: Optional[str] = None) -> None:
        """Emit new data to all connected clients, or to specific target"""
        packet = WebSocketPacket(event, data, to)
        await self._dispatch_queue.put(packet)

    def on(self, event: str, handler: DataCallback) -> None:
        """Listen to an event"""
        if event not in self._listener_callbacks:
            self._listener_callbacks[event] = []
        self._listener_callbacks[event].append(handler)

    def off(self, event: str, handler: Optional[DataCallback] = None):
        """Remove listener from an event"""
        if event not in self._listener_callbacks:
            return
        if handler is None:
            self._listener_callbacks.pop(event, None)
        else:
            self._listener_callbacks[event].remove(handler)
