import asyncio
import hashlib
import logging
import time
from http.cookies import Morsel
from typing import TYPE_CHECKING, Any, Dict

import aiofiles
import aiohttp

from internals.db.models import VTHellJob
from internals.struct import InternalSignalHandler
from internals.utils import find_cookies_file

from .parser import ChatDetails, complex_walk, parse_netscape_cookie_to_morsel, parse_youtube_video_data

if TYPE_CHECKING:
    from internals.vth import SanicVTHell


logger = logging.getLogger("Internals.ChatClient")


class ChatDownloader:
    def __init__(self, video: VTHellJob):
        self.session: aiohttp.ClientSession = None
        self.video = video
        self.logger = logging.getLogger(f"Internals.ChatDownloader[{video.id}]")

    async def create(self):
        cookie_path = await find_cookies_file()
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36",  # noqa
            "Accept-Language": "en-US, en, *",
        }
        self.session = aiohttp.ClientSession(headers=header)
        if cookie_path is not None:
            self.logger.info("Loading cookies from %s", cookie_path)
            async with aiofiles.open(cookie_path, "r") as fp:
                cookies_str = await fp.read()
            try:
                cookie_jar = parse_netscape_cookie_to_morsel(cookies_str)
            except ValueError:
                self.logger.error("Invalid Netscape Cookie File, ignoring cookies!")

            for name, cookie in cookie_jar.items():
                self.session.cookie_jar.update_cookies({name: cookie})
            self.logger.info("Loaded %d cookies", len(cookie_jar))

    async def close(self):
        await self.session.close()

    async def _session_get(self, url: str, **kwargs):
        async with self.session.get(url, **kwargs) as resp:
            return await resp.text(), resp.status

    def _generate_sapisid_header(self):
        sapis_id = None
        sapisid_cookie = None

        for cookie in self.session.cookie_jar:
            if cookie.key == "SAPISID":
                sapis_id = cookie.value
            if cookie.key == "__Secure-3PAPISID":
                sapisid_cookie = cookie.value

        sapisid_cookie = sapisid_cookie or sapis_id
        if sapisid_cookie is None:
            return

        time_now = round(time.time())

        if not sapis_id:
            morsel_sapis = Morsel()
            morsel_sapis.set("SAPISID", sapisid_cookie)
            morsel_sapis["secure"] = True
            morsel_sapis["expires"] = time_now + 3600
            morsel_sapis["domain"] = ".youtube.com"
            morsel_sapis["path"] = "/"
            self.session.cookie_jar.update_cookies({"SAPISID": morsel_sapis})

        sapisid_hash = hashlib.sha1(
            f"{time_now} {sapisid_cookie} https://www.youtube.com".encode("utf-8")
        ).hexdigest()
        return f"SAPISIDHASH {time_now}_{sapisid_hash}"

    def _extract_account_syncid(self, ytcfg):
        sync_ids = ytcfg.get("DATASYNC_ID").split("||")
        if len(sync_ids) >= 2 and sync_ids[1]:
            # datasyncid is of the form "channel_syncid||user_syncid" for secondary channel
            # and just "user_syncid||" for primary channel. We only want the channel_syncid
            return sync_ids[0]

        # ytcfg includes channel_syncid if on secondary channel
        return ytcfg.get("DELEGATED_SESSION_ID")

    def _generate_ytcfg_header(self, ytcfg: Dict[str, Any]):
        headers = {
            "origin": "https://www.youtube.com",
            "x-youtube-client-name": str(ytcfg.get("INNERTUBE_CONTEXT_CLIENT_NAME")),
            "x-youtube-client-version": str(ytcfg.get("INNERTUBE_CLIENT_VERSION")),
            "x-origin": "https://www.youtube.com",
            "x-goog-authuser": "0",
        }

        identity_token = ytcfg.get("ID_TOKEN")
        if identity_token:
            headers["x-youtube-identity-token"] = identity_token

        account_syncid = self._extract_account_syncid(ytcfg)
        if account_syncid:
            headers["x-goog-pageid"] = account_syncid

        session_index = ytcfg.get("SESSION_INDEX")
        if account_syncid or session_index:
            headers["x-goog-authuser"] = session_index or 0

        visitor_data = complex_walk(ytcfg, "INNERTUBE_CONTEXT.client.visitorData")
        if visitor_data:
            headers["x-goog-visitor-id"] = visitor_data

        auth = self._generate_sapisid_header()
        if auth:
            headers["authorization"] = auth

        return headers

    async def _get_yt_initial_data(self, video_id: str):
        url = f"https://youtube.com/watch?v={video_id}"
        self.logger.debug("Fetching initial data from %s", url)
        html, status_code = await self._session_get(url)
        if status_code >= 400:
            self.logger.debug("Failed to fetch initial data from %s", url)
            return

        chat_info = parse_youtube_video_data(html)
        self.logger.debug("Chat information: %s", chat_info)
        return chat_info

    async def _initialize_chat(self, chat_info: ChatDetails):
        if len(chat_info.continuations) < 2:
            raise RuntimeError("Initial continuation information could not be found")

        # Get all messages from the chat
        # continuation = chat_info.continuations[1]

    async def start(self):
        if self.session is None:
            await self.create()
        chat_info = await self._get_yt_initial_data(self.video.id)
        if chat_info is None:
            return
        await self._initialize_chat(chat_info)


class ChatDownloaderManager(InternalSignalHandler):
    signal_name = "internals.chat.client.chatdownloader"

    @staticmethod
    async def main_loop(**context: Dict[str, Any]):
        app: SanicVTHell = context.get("app")
        if app is None:
            logger.error("app context is missing!")
            return
        video: VTHellJob = context.get("video")
        logger.info("Starting chat downloader for %s", video.id)
        chat_downloader = ChatDownloader(video)
        try:
            await chat_downloader.start()
        except asyncio.CancelledError:
            logger.info("Chat downloader for %s was cancelled, flushing...", video.id)
