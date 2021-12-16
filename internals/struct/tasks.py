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
from typing import TYPE_CHECKING, Dict, Type

if TYPE_CHECKING:
    from ..vth import SanicVTHell

__all__ = ("InternalTaskBase",)

logger = logging.getLogger("Tasks.Internal")


class InternalTaskBase:
    _tasks: Dict[str, asyncio.Task] = {}

    @classmethod
    def executor_done(cls: Type[InternalTaskBase], task: asyncio.Task):
        task_name = task.get_name()
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"Task {task_name} failed with exception: {exception}", exc_info=exception)
        except asyncio.exceptions.InvalidStateError:
            pass
        logger.info(f"Task {task_name} finished")
        cls._tasks.pop(task_name, None)

    @classmethod
    async def main_loop(cls: Type[InternalTaskBase], app: SanicVTHell):
        return
