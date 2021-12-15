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
import re
from typing import TYPE_CHECKING, Dict, List, Type

import pendulum

from internals.db import models
from internals.holodex import HolodexVideo
from internals.struct import InternalTaskBase
from internals.utils import secure_filename

if TYPE_CHECKING:
    from internals.vth import SanicVTHell

logger = logging.getLogger("Tasks.AutoScheduler")

__all__ = ("AutoSchedulerTasks",)


def determine_chains(chains: List[Dict[str, str]], data: HolodexVideo):
    if not chains:
        return True
    chains_results = []
    for chain in chains:
        if chain["type"] == "word":
            if chain["data"].casefold() in data.title.casefold():
                chains_results.append(True)
            else:
                chains_results.append(False)
        elif chain["type"] == "regex_word":
            if re.search(chain["data"], data.title, re.IGNORECASE):
                chains_results.append(True)
            else:
                chains_results.append(False)
        elif chain["type"] == "group":
            if data.org and chain["data"].casefold() == data.org.casefold():
                chains_results.append(True)
            else:
                chains_results.append(False)
        elif chain["type"] == "channel":
            if chain["data"] == data.channel_id:
                chains_results.append(True)
            else:
                chains_results.append(False)
    return all(chains_results)


class AutoSchedulerTasks(InternalTaskBase):
    @staticmethod
    async def executor(
        schedulers: List[models.VTHellAutoScheduler], time: int, task_name: str, app: SanicVTHell
    ):
        logger.info(f"Executing auto scheduler job {time} (task {task_name})")
        if len(schedulers) < 1:
            logger.info("No auto schedulers found")
            return

        include = list(filter(lambda x: x.include, schedulers))
        if len(include) < 1:
            logger.warning("No active auto schedulers found")
            return

        exclude = list(filter(lambda x: not x.include, schedulers))
        existing_jobs = await models.VTHellJob.all()
        existing_jobs_ids = [job.id for job in existing_jobs]

        logger.info("Checking Holodex for live and scheduled stream...")
        results = await app.holodex.get_lives()
        if len(results) < 1:
            logger.warning("No lives/upcoming stream found from Holodex")
            return
        logger.info(f"Found {len(results)} live/upcoming stream(s)")

        exclude_ids = list(
            map(lambda x: x.data, filter(lambda x: x.type == models.VTHellAutoType.channel, exclude))
        )
        exclude_groups = list(
            map(lambda x: x.data.casefold(), filter(lambda x: x.type == models.VTHellAutoType.group, exclude))
        )
        word_blacklist = list(
            map(lambda x: x.data, filter(lambda x: x.type == models.VTHellAutoType.word, exclude))
        )
        regex_blacklist = list(
            map(
                lambda x: re.compile(x.data, re.I),
                filter(lambda x: x.type == models.VTHellAutoType.regex_word, exclude),
            )
        )

        logger.info("Filtering results with exclude filters...")
        filtered_videos: List[HolodexVideo] = []
        for video in results:
            if video.channel_id in exclude_ids:
                continue
            if video.org and video.org in exclude_groups:
                continue
            skip_it = False
            for blacklist in word_blacklist:
                if blacklist.casefold() in video.title.casefold():
                    skip_it = True
                    break
            if skip_it:
                continue
            skip_it = False
            for blacklist in regex_blacklist:
                if blacklist.search(video.title) is not None:
                    skip_it = True
                    break
            if skip_it:
                continue
            filtered_videos.append(video)

        if len(filtered_videos) < 1:
            logger.warning("No videos found to be scheduled since all of them got filtered at the start")
            return

        include_ids = list(
            map(lambda x: x.data, filter(lambda x: x.type == models.VTHellAutoType.channel, include))
        )
        include_groups = list(
            map(lambda x: x.data.casefold(), filter(lambda x: x.type == models.VTHellAutoType.group, include))
        )
        word_whitelist = list(filter(lambda x: x.type == models.VTHellAutoType.word, include))
        regex_whitelist = list(filter(lambda x: x.type == models.VTHellAutoType.regex_word, include))

        logger.info("Filtering results with include filters...")
        double_filtered_videos: List[HolodexVideo] = []
        for video in filtered_videos:
            if video.channel_id in include_ids:
                double_filtered_videos.append(video)
                continue
            if video.org and video.org.casefold() in include_groups:
                double_filtered_videos.append(video)
                continue
            include_it = False
            for whitelist in word_whitelist:
                if whitelist.data.casefold() in video.title.casefold():
                    if determine_chains(whitelist.chains, video):
                        include_it = True
                        break
            if include_it:
                double_filtered_videos.append(video)
                continue
            include_it = False
            for whitelist in regex_whitelist:
                if whitelist.search(video.title) is not None:
                    if determine_chains(whitelist.chains, video):
                        include_it = True
                        break
            if include_it:
                double_filtered_videos.append(video)
                continue

        if len(double_filtered_videos) < 1:
            logger.warning("No videos found to be schedule with both include/exclude filters")
            return

        deduplicated_videos: List[HolodexVideo] = []
        for video in double_filtered_videos:
            if video.id in existing_jobs_ids:
                continue
            deduplicated_videos.append(video)

        import pprint

        pprint.pprint(deduplicated_videos)

        # Add to database/schedule it
        logger.info(f"Adding {len(double_filtered_videos)} videos to the jobs scheduler")
        executed_videos = []
        for video in double_filtered_videos:
            if video.id in executed_videos:
                logger.warning(f"Video <{video.id}> already scheduled, skipping")
                continue
            title_safe = secure_filename(video.title)
            utc_unix = pendulum.from_timestamp(video.start_time, tz="UTC")
            as_jst = utc_unix.in_timezone("Asia/Tokyo")
            filename = f"[{as_jst.year}.{as_jst.month}.{as_jst.day}.{video.id}] {title_safe}"
            job = models.VTHellJob(
                id=video.id,
                title=video.title,
                filename=filename,
                start_time=video.start_time,
                channel_id=video.channel_id,
                member_only=video.is_member,
            )
            logger.info(f"Scheduling <{video.id}> from Autoscheduler run {time}")
            await job.save()
            executed_videos.append(video.id)
            await app.sio.emit(
                "job_scheduled",
                {
                    "id": job.id,
                    "title": job.title,
                    "start_time": job.start_time,
                    "channel_id": job.channel_id,
                    "is_member": job.member_only,
                    "status": job.status.value,
                },
                namespace="/vthell",
            )

    @classmethod
    def executor_done(cls: Type[AutoSchedulerTasks], task: asyncio.Task):
        task_name = task.get_name()
        try:
            exception = task.exception()
            if exception is not None:
                logger.error(f"Task {task_name} failed with exception: {exception}", exc_info=exception)
        except asyncio.exceptions.InvalidStateError:
            pass
        logger.info(f"Task {task_name} finished")
        cls._tasks.pop(task_name, None)

    @staticmethod
    async def get_auto_schedulers():
        return await models.VTHellAutoScheduler.all()

    @classmethod
    async def main_loop(cls: Type[AutoSchedulerTasks], app: SanicVTHell):
        loop = app.loop
        config = app.config
        await app.wait_until_ready()
        try:
            while True:
                ctime = pendulum.now("UTC").int_timestamp
                logger.info(f"Checking for auto scheduler at {ctime}")
                all_tasks = []
                task_name = f"auto-scheduler-{ctime}"
                task = loop.create_task(
                    cls.executor(await cls.get_auto_schedulers(), ctime, task_name, app), name=task_name
                )
                task.add_done_callback(cls.executor_done)
                all_tasks.append(task)
                if not all_tasks:
                    logger.info("No auto scheduler found")
                await asyncio.gather(*all_tasks)
                await asyncio.sleep(config.VTHELL_LOOP_SCHEDULER)
        except asyncio.CancelledError:
            logger.warning("Got cancel signal, cleaning up all running tasks")
            for task in cls._tasks.values():
                task.cancel()
