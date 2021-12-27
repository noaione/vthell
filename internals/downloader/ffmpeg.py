import asyncio
import logging
from typing import TYPE_CHECKING, Dict, List

from internals.db.models import VTHellJobStatus

from ._shared import quick_update_dispatch

if TYPE_CHECKING:
    from internals.db.models import VTHellJob
    from internals.vth import SanicVTHell


logger = logging.getLogger("Internals.FFMPEGDownloader")
__all__ = ("download_via_ffmpeg",)


async def download_via_ffmpeg(
    app: SanicVTHell,
    data: VTHellJob,
    urls: List[str],
    output_file: str,
    http_headers: Dict[str, str] = None,
    extra_args: Dict[str, str] = None,
):
    ffmpeg_args = [app.config.FFMPEG_PATH, "-hide_banner", "-v", "verbose"]
    if isinstance(http_headers, dict):
        ffmpeg_args.extend(
            [
                "-headers",
                "".join(f"{k}: {v}\r\n" for k, v in http_headers.items()),
            ]
        )
    if isinstance(extra_args, dict):
        for key, val in extra_args.items():
            ffmpeg_args.extend([key, val])
    for url in urls:
        ffmpeg_args.extend(["-i", url])
    ffmpeg_args.extend(["-c", "copy", str(output_file), "-y"])
    logger.debug(f"Executing ffmpeg with args: {ffmpeg_args}")
    # Only pipe stderr since stdout is the actual data.
    ffmpeg_process = await asyncio.create_subprocess_exec(
        *ffmpeg_args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )

    is_error = False
    already_announced = False
    error_line = None
    while True:
        try:
            async for line in ffmpeg_process.stderr:
                line = line.decode("utf-8").rstrip()
                lower_line = line.lower()
                if "press [q] to stop" in lower_line or ("press" in lower_line and "stop" in lower_line):
                    if not already_announced:
                        already_announced = True
                        await quick_update_dispatch(
                            data,
                            app,
                            VTHellJobStatus.downloading,
                            True,
                            {"resolution": data.resolution or "Unknown"},
                        )
                elif "io error" in lower_line:
                    logger.error(f"[{data.id}] ffmpeg: IO error, cancelling...")
                    is_error = True
                    error_line = line
                    break
                logger.debug(f"[{data.id}] ffmpeg: {line}")
        except ValueError:
            logger.debug(f"[{data.id}] ffmpeg: buffer exceeded, silently ignoring...")
            continue
        else:
            break

    await ffmpeg_process.wait()
    ret_code = ffmpeg_process.returncode
    return ret_code, is_error, error_line
