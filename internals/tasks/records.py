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
from hashlib import md5
from typing import TYPE_CHECKING, List, Optional, Type, TypedDict

import orjson
import pendulum

from internals.struct import InternalTaskBase, VTHellRecords

if TYPE_CHECKING:
    from pendulum.datetime import DateTime
    from pendulum.period import Period

    from internals.vth import SanicVTHell


logger = logging.getLogger("Tasks.Records")


class RCloneListJson(TypedDict):
    Path: str
    Name: str
    Size: int
    MimeType: str
    ModTime: str
    IsDir: bool


def next_run() -> int:
    # Check at what time the next run should be
    # Run every 1 hour
    # So pad the current time with the next hour
    end_of: DateTime = pendulum.now().end_of("hour")
    return end_of.add(microseconds=1)


async def wait_next_run():
    current_time = pendulum.now()
    next_run_time = next_run()
    delta_left: Period = next_run_time - current_time
    delta_second = delta_left.seconds
    if delta_second < 0:
        return
    logger.info(f"Waiting {delta_second} seconds before next run...")
    await asyncio.sleep(delta_second)


def hash_path(path: str) -> str:
    return md5(path.encode()).hexdigest()


def find_node(dataset: List[VTHellRecords], name: str):
    for idx, data in enumerate(dataset):
        if name == data.name:
            return idx
    return -1


def utcstamp_to_unix(isodate: Optional[str]) -> Optional[int]:
    if not isodate:
        return None
    as_utc = pendulum.parse(isodate).set(tz="UTC")
    return int(round(as_utc.timestamp()))


VALID_SUBFOLDER = [
    "Chat Archive",
    "Member-Only Chat Archive",
    "Stream Archive",
    "Member-Only Stream Archive",
]


class RecordedStreamTasks(InternalTaskBase):
    @staticmethod
    async def executor(task_name: str, app: SanicVTHell):
        logger.info(f"Running task {task_name}")
        if app.config.RCLONE_DISABLE:
            logger.warning("Rclone is disabled, skipping task")
            return

        rclone_path = app.config.RCLONE_PATH
        drive_target = app.config.RCLONE_DRIVE_TARGET

        rclone_args = [rclone_path, "lsjson", "-R", drive_target]
        logger.debug(f"Running rclone command: {rclone_args}")
        rclone_process = await asyncio.create_subprocess_exec(
            *rclone_args, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )
        stdout, stderr = await rclone_process.communicate()
        stdout = stdout.decode("utf-8").rstrip("\n")
        stderr = stderr.decode("utf-8").strip("\n")
        rc_code = rclone_process.returncode
        if rc_code != 0:
            if not stderr:
                stderr = stdout
            logger.error(f"Rclone failed with code {rc_code}\n{stderr}")
            return

        # Parse the output
        logger.info("Parsing rclone output...")
        try:
            subfolder_data: List[RCloneListJson] = orjson.loads(stdout)
        except Exception as e:
            logger.error(f"Failed to decode json: {e}", exc_info=e)
            return

        filtered_paths: List[RCloneListJson] = []
        for file in subfolder_data:
            split_path = file["Path"].split("/", 1)
            if len(split_path) == 1:
                if split_path[0] in VALID_SUBFOLDER:
                    filtered_paths.append(file)
            else:
                base_folder, _ = split_path
                if base_folder in VALID_SUBFOLDER:
                    filtered_paths.append(file)

        if len(filtered_paths) < 1:
            logger.info("No files found, skipping task")
            return

        filtered_paths.sort(key=lambda x: x["Path"])
        total_size = 0
        base_state = VTHellRecords(id="vthell", name="VTuberHell", type="folder", toggled=True, children=[])
        for file in filtered_paths:
            folders = file["Path"].split("/")
            if file["IsDir"] and len(folders) == 1:
                base_state.children.append(
                    VTHellRecords(
                        id=hash_path(file["Path"]),
                        name=file["Path"],
                        type="folder",
                        toggled=True,
                        children=[],
                    )
                )
                continue
            folders, files = folders[:-1], folders[-1]
            use_base = base_state
            for folder in folders:
                node_idx = find_node(use_base.children, folder)
                if node_idx == -1:
                    use_base.children.append(
                        VTHellRecords(
                            id=hash_path(file["Path"]), name=folder, type="folder", toggled=False, children=[]
                        )
                    )
                    node_idx = find_node(use_base.children, folder)
                    use_base = use_base.children[node_idx]
                    continue
                use_base = use_base.children[node_idx]
            if file["IsDir"]:
                use_base.children.append(
                    VTHellRecords(
                        id=hash_path(file["Path"]), name=files, type="folder", toggled=False, children=[]
                    )
                )
            else:
                total_size += file["Size"]
                sub_data = VTHellRecords(
                    id=hash_path(file["Path"]),
                    name=files,
                    type="file",
                    size=file["Size"],
                    mimetype=file.get("MimeType", "application/octet-stream"),
                    modtime=utcstamp_to_unix(file.get("ModTime")),
                )
                use_base.children.append(sub_data)

        # Save the data
        logger.info("Updating records...")
        app.vtrecords.update(base_state, total_size)

    @classmethod
    async def main_loop(cls: Type[RecordedStreamTasks], app: SanicVTHell):
        await app.wait_until_ready()
        if app.vtrecords.data is None:
            logger.info("No records found, running main task now!")
            await RecordedStreamTasks.executor("RecordInitialization", app)
        try:
            while True:
                await wait_next_run()
                ctime = pendulum.now("UTC").int_timestamp
                task_name = f"RecordsUpdater-{ctime}"
                task = app.loop.create_task(cls.executor(task_name, app), name=task_name)
                task.add_done_callback(cls.executor_done)
                cls._tasks[task_name] = task
        except asyncio.CancelledError:
            logger.warning("Got cancel signal, cleaning up all running tasks")
            for name, task in cls._tasks.items():
                if name.startswith("RecordsUpdater"):
                    task.cancel()
