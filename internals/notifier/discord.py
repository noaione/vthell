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

import logging
from typing import TYPE_CHECKING, Any, Dict

import aiohttp
from discord_webhook import DiscordEmbed, DiscordWebhook

from internals.db import models
from internals.struct import InternalSignalHandler

if TYPE_CHECKING:
    from ..vth import SanicVTHell

logger = logging.getLogger("Notifier.Discord")
__all__ = ("DiscordNotificationHandler",)


def make_update_discord_embed(data: models.VTHellJob):
    url = f"https://youtu.be/{data.id}"
    if data.status == models.VTHellJobStatus.downloading:
        desc = f"Recording started!\n**{data.filename}**\n\nURL: {url}"
        embed = DiscordEmbed(title="VTHell Start", description=desc, color="a49be6")
    elif data.status == models.VTHellJobStatus.error:
        desc = f"An error occured\nURL: {url}\n\n{data.error}"
        embed = DiscordEmbed(title="VTHell Error", description=desc, color="b93c3c")
    elif data.status in [models.VTHellJobStatus.cleaning, models.VTHellJobStatus.done]:
        desc = f"Recording finished!\n**{data.filename}**\n\n**Link**\n[Stream]({url})"
        embed = DiscordEmbed(title="VTHell Finished", description=desc, color="9fe69b")
    elif data.status in [models.VTHellJobStatus.uploading]:
        desc = f"Uploading started!\n**{data.filename}**\n\nURL: {url}"
        embed = DiscordEmbed(title="VTHell Downloaded", description=desc, color="9bc3e6")
    else:
        return None

    embed.set_image(url=f"https://i.ytimg.com/vi/{data.id}/maxresdefault.jpg")
    embed.set_timestamp()
    webhook = DiscordWebhook(url="")
    webhook.add_embed(embed)
    return webhook.get_embeds()[0]


def make_schedule_discord_embed(data: models.VTHellJob):
    embed = DiscordEmbed(title="VTHell Scheduler", color="cfdf69")
    url = f"https://youtu.be/{data.id}"
    embed.set_description(f"**{data.filename}**\n[Link]({url})")
    embed.set_image(url=f"https://i.ytimg.com/vi/{data.id}/maxresdefault.jpg")
    webhook = DiscordWebhook(url="")
    webhook.add_embed(embed)
    return webhook.get_embeds()[0]


async def one_time_shot(embed: Dict[str, Any], url: str):
    if embed is None or url is None:
        return

    params = {"wait": "true"}
    json_files = {"embeds": [embed], "username": "VTHell", "avatar_url": "https://p.n4o.xyz/i/cococlock.png"}
    header = {"User-Agent": "VTHell/3.0 (+https://github.com/noaione/vthell)"}
    async with aiohttp.ClientSession(headers=header) as session:
        async with session.post(url, json=json_files, params=params) as resp:
            if resp.status >= 400:
                logger.error(f"Discord webhook returned {resp.status}")
            logger.info(f"Sent discord webhook to {url}")


class DiscordNotificationHandler(InternalSignalHandler):
    signal_name = "internals.notifier.discord"

    @staticmethod
    async def main_loop(**context: Dict[str, Any]):
        app: SanicVTHell = context.get("app")
        if app is None:
            logger.error("app context is missing!")
            return
        logger.info("Building Discord Webhook embed...")
        data: models.VTHellJob = context.get("data")
        if data is None:
            logger.error("data context is missing!")
            return
        emit_type = context.get("type", "update")
        webhook_url: str = app.config.get("NOTIFICATION_DISCORD_WEBHOOK", "").strip()
        if webhook_url == "":
            logger.error("Discord webhook URL is empty, skipping notification")
            return

        if emit_type == "update":
            embeds = make_update_discord_embed(data)
            if embeds is None:
                logger.debug("No embeds to send for update signal")
            await one_time_shot(embeds, webhook_url)
        elif emit_type == "schedule":
            embeds = make_schedule_discord_embed(data)
            await one_time_shot(embeds, webhook_url)
