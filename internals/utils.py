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

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import aiofiles.ospath

__all__ = (
    "secure_filename",
    "find_binary",
    "find_ytarchive_binary",
    "find_rclone_binary",
    "find_mkvmerge_binary",
    "test_rclone_binary",
    "test_ytarchive_binary",
    "test_mkvmerge_binary",
    "build_rclone_path",
    "find_cookies_file",
    "find_cookies_file_sync",
    "map_to_boolean",
)


def secure_filename(fn: str):
    replacement = {
        "/": "／",
        ":": "：",
        "<": "＜",
        ">": "＞",
        '"': "”",
        "'": "’",
        "\\": "＼",
        "?": "？",
        "*": "⋆",
        "|": "｜",
        "#": "",
    }
    for k, v in replacement.items():
        fn = fn.replace(k, v)
    EMOJI_PATTERN = re.compile(
        "(["
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "])"
    )
    fn = re.sub(EMOJI_PATTERN, "_", fn)
    return fn


def find_binary(filename: str):
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        exe_file = os.path.join(path, filename)
        if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
            return exe_file
    return None


def find_ytarchive_binary():
    return find_binary("ytarchive") or find_binary("ytarchive.exe")


def find_rclone_binary():
    return find_binary("rclone") or find_binary("rclone.exe")


def find_mkvmerge_binary():
    return find_binary("mkvmerge") or find_binary("mkvmerge.exe")


def test_rclone_binary(path: str, drive_target: str):
    if not drive_target:
        return False
    if not drive_target.endswith(":"):
        drive_target = drive_target + ":"

    rclone_cmd = [path, "lsd", drive_target]

    try:
        cmd = subprocess.Popen(rclone_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return False
    ret_code = cmd.wait()
    return ret_code == 0


def test_ytarchive_binary(path: str):
    ytarchive_cmd = [path, "--version"]

    try:
        cmd = subprocess.Popen(ytarchive_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return False
    ret_code = cmd.wait()
    return ret_code == 0


def test_mkvmerge_binary(path: str):
    mkvmerge_cmd = [path, "--version"]

    try:
        cmd = subprocess.Popen(mkvmerge_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return False
    ret_code = cmd.wait()
    return ret_code == 0


def build_rclone_path(drive_base: str, *targets: str):
    merge_target = "/"
    for target in targets:
        if not isinstance(target, str):
            target = str(target)
        merge_target += target + "/"
    if merge_target.endswith("/"):
        merge_target = merge_target[:-1]
    if "/" in drive_base and ":" in drive_base:
        # Assume that it's a drive then directory
        if drive_base.endswith("/"):
            drive_base = drive_base[:-1]
        return drive_base + merge_target
    elif ":" in drive_base and drive_base.endswith(":"):
        # Assume that it's a drive
        return drive_base + merge_target[1:]
    else:
        return drive_base + ":" + merge_target[1:]


def find_cookies_file_sync():
    CURRENT_PATH = Path(__file__).absolute().parent.parent
    cookies_files = [
        CURRENT_PATH / "cookies.txt",
        CURRENT_PATH / "cookie.txt",
        CURRENT_PATH / "membercookies.txt",
        CURRENT_PATH / "membercookie.txt",
    ]

    for cookie_file in cookies_files:
        if os.path.isfile(cookie_file) and os.path.exists(cookie_file):
            return cookie_file
    return None


async def find_cookies_file():
    CURRENT_PATH = Path(__file__).absolute().parent.parent
    cookies_files = [
        CURRENT_PATH / "cookies.txt",
        CURRENT_PATH / "cookie.txt",
        CURRENT_PATH / "membercookies.txt",
        CURRENT_PATH / "membercookie.txt",
    ]

    for cookie_file in cookies_files:
        is_file = await aiofiles.ospath.isfile(cookie_file)
        if is_file:
            file_exists = await aiofiles.ospath.exists(cookie_file)
            if file_exists:
                return cookie_file
    return None


def map_to_boolean(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.lower() in ["true", "yes", "1", "y"]
    elif isinstance(value, int):
        return value > 0
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    try:
        return bool(value)
    except Exception:
        return False
