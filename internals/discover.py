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

import inspect
import logging
from glob import glob
from importlib import import_module, util
from inspect import getmembers
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Dict, Union

from sanic.blueprints import Blueprint

from .struct import InternalSignalHandler, InternalSocketHandler, InternalTaskBase

if TYPE_CHECKING:
    from .vth import SanicVTHell


__all__ = ("autodiscover",)

logger = logging.getLogger("internals.discover")


def autodiscover(app: SanicVTHell, *module_names: Union[str, ModuleType], recursive: bool = False):
    mod = app.__module__
    blueprints: Dict[str, Blueprint] = {}
    socket_routes: Dict[str, InternalSocketHandler] = {}
    tasks: Dict[str, InternalTaskBase] = {}
    signals: Dict[str, InternalSignalHandler] = {}
    _imported = set()

    def _find_bps(module):
        nonlocal blueprints
        nonlocal tasks

        for _, member in getmembers(module):
            if isinstance(member, Blueprint):
                logger.info("Found blueprint: %s", member.name)
                blueprints[member.name] = member

        for _, member in getmembers(module, inspect.isclass):
            cls_name = member.__name__
            if issubclass(member, InternalTaskBase):
                if cls_name == InternalTaskBase.__name__:
                    continue
                logger.info("Found task: %s", cls_name)
                tasks[cls_name] = member
            elif issubclass(member, InternalSocketHandler):
                if cls_name == InternalSocketHandler.__name__:
                    continue
                logger.info("Found socket handler: %s", cls_name)
                socket_routes[cls_name] = member
            elif issubclass(member, InternalSignalHandler):
                if cls_name == InternalSignalHandler.__name__:
                    continue
                logger.info("Found signal handler: %s", cls_name)
                signals[cls_name] = member

    for module in module_names:
        if isinstance(module, str):
            module = import_module(module, mod)
            _imported.add(module.__file__)
        _find_bps(module)

        if recursive:
            base = Path(module.__file__).parent
            for path in glob(f"{base}/**/*.py", recursive=True):
                if path not in _imported:
                    name = "module"
                    if "__init__" in path:
                        *_, name, __ = path.replace("\\", "/").split("/")
                    spec = util.spec_from_file_location(name, path)
                    specmod = util.module_from_spec(spec)
                    _imported.add(path)
                    try:
                        spec.loader.exec_module(specmod)
                    except ModuleNotFoundError:
                        continue
                    _find_bps(specmod)

    for bp_name, bp_routes in blueprints.items():
        logger.info("Registering blueprint: %s", bp_name)
        app.blueprint(bp_routes)
    for task_name, task_cls in tasks.items():
        logger.info("Registering task: %s", task_name)
        app.add_task(task_cls.main_loop)
    for eio_n, eio_v in socket_routes.items():
        logger.info("Registering socket handler: %s", eio_n)
        eio_v.attach(app)
    for sig_n, sig_val in signals.items():
        logger.info("Registering signal handler: %s", sig_n)
        try:
            setattr(sig_val.main_loop, "__requirements__", None)
        except AttributeError:
            pass
        app.add_signal(sig_val.main_loop, sig_val.signal_name)
