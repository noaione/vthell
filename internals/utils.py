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

import asyncio
import logging
import os
import random
import re
import string as pystring
import subprocess
from http.cookies import Morsel
from pathlib import Path
from typing import IO, Any, Dict, NoReturn, Union
from urllib.parse import quote as url_quote

import aiofiles.ospath
import pendulum

__all__ = (
    "secure_filename",
    "find_binary",
    "find_ytarchive_binary",
    "find_rclone_binary",
    "find_mkvmerge_binary",
    "find_ffmpeg_binary",
    "test_rclone_binary",
    "test_ytarchive_binary",
    "test_mkvmerge_binary",
    "test_ffmpeg_binary",
    "build_rclone_path",
    "find_cookies_file",
    "find_cookies_file_sync",
    "map_to_boolean",
    "rng_string",
    "acquire_file_lock",
    "remove_acquired_lock",
    "parse_expiry_as_date",
    "parse_cookie_to_morsel",
    "get_indexed",
    "complex_walk",
)

logger = logging.getLogger("Internals.Utils")
BASE_PATH = Path(__file__).absolute().parent.parent


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


def find_ffmpeg_binary():
    return find_binary("ffmpeg") or find_binary("ffmpeg.exe")


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


def test_ffmpeg_binary(path: str):
    ffmpeg_cmd = [path, "-version"]

    try:
        cmd = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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


def rng_string(length: int) -> str:
    all_strings = pystring.ascii_letters + pystring.digits
    contents = [random.choice(all_strings) for _ in range(length)]
    return "".join(contents)


class AcquiringLockError(Exception):
    pass


class ReleaseLockError(Exception):
    def __init__(self, exc: Exception) -> None:
        self.original_error = exc
        super().__init__("An error occured while trying to unlock lock file")


def _acquire_lock_windows(file: IO):
    import msvcrt

    mode = msvcrt.LK_NBLCK
    savepos = file.tell()
    if savepos:
        file.seek(0)
    try:
        msvcrt.locking(file.fileno(), mode, int(2 ** 31 - 1))
    except IOError:
        raise AcquiringLockError("Could not acquire lock")
    if savepos:
        file.seek(savepos)


def _release_lock_windows(file: IO):
    import msvcrt

    import pywintypes  # type: ignore
    import win32file  # type: ignore
    import winerror  # type: ignore

    __overlapped = pywintypes.OVERLAPPED()
    savepos = file.tell()
    if savepos:
        file.seek(0)
    try:
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, int(2 ** 31 - 1))
    except IOError as exc:
        if exc.strerror == "Permission denied":
            hfile = win32file._get_osfhandle(file.fileno())
            try:
                win32file.UnlockFileEx(hfile, 0, -0x10000, __overlapped)
            except pywintypes.error as exc2:
                if exc2.winerror == winerror.ERROR_NOT_LOCKED:
                    pass
                else:
                    raise ReleaseLockError(exc2)
        else:
            raise ReleaseLockError(exc)
    finally:
        if savepos:
            file.seek(savepos)


def _acquire_lock_unix(file: IO):
    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)
    except BlockingIOError:
        raise AcquiringLockError("Could not acquire lock")


def _release_lock_unix(file: IO):
    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        raise ReleaseLockError(e)


def _acquire_lock(file: IO):
    import sys

    if sys.platform == "win32":
        # _acquire_lock_windows(file)
        pass
    else:
        _acquire_lock_unix(file)


def _release_lock(file: IO):
    import sys

    if sys.platform == "win32":
        # _release_lock_windows(file)
        pass
    else:
        _release_lock_unix(file)


async def acquire_file_lock(loop: asyncio.AbstractEventLoop = None) -> bool:
    loop = loop or asyncio.get_event_loop()
    db_path = BASE_PATH / "dbs" / "vthell-server_do_not_delete.lock"

    fp = await loop.run_in_executor(None, open, str(db_path), "w")
    try:
        logger.info("Acquiring file lock")
        await loop.run_in_executor(None, _acquire_lock, fp)
        logger.info("Acquired file lock, running as server mode")
    except AcquiringLockError:
        logger.info("Failed to acquire file lock, running as client mode")
        return False
    await loop.run_in_executor(None, fp.close)
    return True


async def remove_acquired_lock(loop: asyncio.AbstractEventLoop = None) -> NoReturn:
    loop = loop or asyncio.get_event_loop()
    db_path = BASE_PATH / "dbs" / "vthell-server_do_not_delete.lock"

    try:
        fp = await loop.run_in_executor(None, open, str(db_path), "w")
    except FileNotFoundError:
        logger.error("Failed to remove acquired lock, file not found")
        return
    try:
        logger.info("Removing acquired lock")
        await loop.run_in_executor(None, _release_lock, fp)
        logger.info("Removed acquired lock")
    except ReleaseLockError as exc:
        logger.error("Failed to remove acquired lock", exc_info=exc.original_error)
        return
    await loop.run_in_executor(None, fp.close)

    try:
        # Cleanup
        await loop.run_in_executor(None, db_path.unlink)
    except Exception:
        return


def parse_expiry_as_date(expiry: int):
    date = pendulum.from_timestamp(expiry)
    return date.format("ddd, DD MMM YYYY HH:mm:ss") + " GMT"


def parse_cookie_to_morsel(cookie_content: str):
    split_lines = cookie_content.splitlines()
    valid_header = split_lines[0].lower().startswith("# netscape")
    if not valid_header:
        raise ValueError("Invalid Netscape Cookie File")

    netscape_cookies: Dict[str, Morsel] = {}
    for line in split_lines[1:]:
        if not line:
            continue
        if line.startswith("#"):
            continue
        try:
            domain, flag, path, secure, expiration, name, value = line.split("\t")
        except Exception:
            raise ValueError("Invalid Netscape Cookie File")

        flag = flag.lower() == "true"
        secure = secure.lower() == "true"
        expiration = int(expiration)
        cookie = Morsel()
        cookie.set(name, value, url_quote(value))
        cookie["domain"] = domain
        cookie["path"] = path
        cookie["secure"] = secure
        cookie["expires"] = parse_expiry_as_date(expiration)
        cookie["httponly"] = True
        netscape_cookies[name] = cookie

    return netscape_cookies


def get_indexed(data: list, n: int):
    if not data:
        return None
    try:
        return data[n]
    except (ValueError, IndexError):
        return None


def complex_walk(dictionary: Union[dict, list], paths: str):
    if not dictionary:
        return None
    expanded_paths = paths.split(".")
    skip_it = False
    for n, path in enumerate(expanded_paths):
        if skip_it:
            skip_it = False
            continue
        if path.isdigit():
            path = int(path)  # type: ignore
        if path == "*" and isinstance(dictionary, list):
            new_concat = []
            next_path = get_indexed(expanded_paths, n + 1)
            if next_path is None:
                return None
            skip_it = True
            for content in dictionary:
                try:
                    new_concat.append(content[next_path])
                except (TypeError, ValueError, IndexError, KeyError, AttributeError):
                    pass
            if len(new_concat) < 1:
                return new_concat
            dictionary = new_concat
            continue
        try:
            dictionary = dictionary[path]  # type: ignore
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None
    return dictionary


def try_use_uvloop() -> None:
    """
    Use uvloop instead of the default asyncio loop.
    """
    if os.name == "nt":
        logger.warning(
            "You are trying to use uvloop, but uvloop is not compatible "
            "with your system. You can disable uvloop completely by setting "
            "the 'USE_UVLOOP' configuration value to false, or simply not "
            "defining it and letting Sanic handle it for you. Sanic will now "
            "continue to run using the default event loop."
        )
        return

    try:
        import uvloop  # type: ignore
    except ImportError:
        logger.warning(
            "You are trying to use uvloop, but uvloop is not "
            "installed in your system. In order to use uvloop "
            "you must first install it. Otherwise, you can disable "
            "uvloop completely by setting the 'USE_UVLOOP' "
            "configuration value to false. Sanic will now continue "
            "to run with the default event loop."
        )
        return

    uvloop_install_removed = map_to_boolean(os.getenv("SANIC_NO_UVLOOP", "no"))
    if uvloop_install_removed:
        logger.info(
            "You are requesting to run Sanic using uvloop, but the "
            "install-time 'SANIC_NO_UVLOOP' environment variable (used to "
            "opt-out of installing uvloop with Sanic) is set to true. If "
            "you want to prevent Sanic from overriding the event loop policy "
            "during runtime, set the 'USE_UVLOOP' configuration value to "
            "false."
        )

    if not isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy):
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
