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

import glob
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import coloredlogs

__all__ = ("RollingFileHandler", "setup_logger")


class RollingFileHandler(RotatingFileHandler):
    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False,
    ) -> None:
        self._last_backup_count = 0
        super().__init__(
            filename, mode=mode, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding, delay=delay
        )
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self._determine_start_count()

    def _determine_start_count(self):
        all_files = glob.glob(self.baseFilename + "*")
        if all_files:
            all_files.sort()
            last_digit = all_files[-1].split(".")[-1]
            if last_digit.isdigit():
                self._last_backup_count = int(last_digit)

    def doRollover(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
        self._last_backup_count += 1
        next_name = "%s.%d" % (self.baseFilename, self._last_backup_count)
        self.rotate(self.baseFilename, next_name)
        if not self.delay:
            self.stream = self._open()


def setup_logger(log_path: Path):
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "nvthell.log"

    file_handler = RollingFileHandler(log_file, maxBytes=5_242_880, backupCount=5, encoding="utf-8")
    # Reset all logger
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler],
        format="[%(asctime)s] - (%(name)s)[%(levelname)s](%(funcName)s): %(message)s",  # noqa: E501
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger()
    coloredlogs.install(
        fmt="[%(asctime)s %(hostname)s][%(levelname)s] (%(name)s[%(process)d]): %(funcName)s: %(message)s",
        level=logging.INFO,
        logger=logger,
        stream=sys.stdout,
    )

    # Set default logging for some modules
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("chardet").setLevel(logging.WARNING)

    # Set back to the default of INFO even if asyncio's debug mode is enabled.
    logging.getLogger("asyncio").setLevel(logging.INFO)

    return logger
