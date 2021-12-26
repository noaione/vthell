"""
MIT License

Copyright (c) 2020-present noaione, xenova

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
import hashlib
import logging
import time
from enum import Enum
from http.cookies import Morsel
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import quote as url_quote

import aiofiles
import aiohttp
import pendulum

from internals.chat.errors import ChatDisabled, LoginRequired, NoChatReplay, VideoUnavailable, VideoUnplayable
from internals.chat.parser import (
    ChatDetails,
    YoutubeChatParser,
    complex_walk,
    parse_initial_data,
    parse_youtube_video_data,
)
from internals.chat.utils import camel_case_split, remove_prefixes, remove_suffixes, try_get_first_key
from internals.utils import find_cookies_file, parse_cookie_to_morsel, parse_expiry_as_date

if TYPE_CHECKING:
    from internals.chat.writer import JSONWriter

__all__ = ("ChatDownloader",)


class ChatEvent(Enum):
    data = 0
    wait = 1


class ChatDownloader:
    def __init__(self, video_id: str):
        self.session: aiohttp.ClientSession = None
        self.video_id = video_id
        self.logger = logging.getLogger(f"Internals.ChatDownloader[{video_id}]")

    # KNOWN ACTIONS AND MESSAGE TYPES
    _KNOWN_ADD_TICKER_TYPES = {
        "addLiveChatTickerItemAction": [
            "liveChatTickerSponsorItemRenderer",
            "liveChatTickerPaidStickerItemRenderer",
            "liveChatTickerPaidMessageItemRenderer",
        ]
    }

    _KNOWN_ADD_ACTION_TYPES = {
        "addChatItemAction": [
            # message saying Live Chat replay is on
            "liveChatViewerEngagementMessageRenderer",
            "liveChatMembershipItemRenderer",
            "liveChatTextMessageRenderer",
            "liveChatPaidMessageRenderer",
            "liveChatPlaceholderItemRenderer",  # placeholder
            "liveChatDonationAnnouncementRenderer",
            "liveChatPaidStickerRenderer",
            "liveChatModeChangeMessageRenderer",  # e.g. slow mode enabled
            # TODO find examples of:
            # 'liveChatPurchasedProductMessageRenderer',  # product purchased
            # liveChatLegacyPaidMessageRenderer
            # liveChatModerationMessageRenderer
            # liveChatAutoModMessageRenderer
        ]
    }

    _KNOWN_REPLACE_ACTION_TYPES = {
        "replaceChatItemAction": ["liveChatPlaceholderItemRenderer", "liveChatTextMessageRenderer"]
    }
    # actions that have an 'item'
    _KNOWN_ITEM_ACTION_TYPES = {**_KNOWN_ADD_TICKER_TYPES, **_KNOWN_ADD_ACTION_TYPES}
    # [message deleted] or [message retracted]
    _KNOWN_REMOVE_ACTION_TYPES = {
        "markChatItemsByAuthorAsDeletedAction": ["banUser"],  # TODO ban?  # deletedStateMessage
        "markChatItemAsDeletedAction": ["deletedMessage"],  # deletedStateMessage
    }

    _KNOWN_ADD_BANNER_TYPES = {
        "addBannerToLiveChatCommand": [
            "liveChatBannerRenderer",
            "liveChatBannerHeaderRenderer" "liveChatTextMessageRenderer",
        ]
    }
    _KNOWN_REMOVE_BANNER_TYPES = {"removeBannerForLiveChatCommand": ["removeBanner"]}  # targetActionId
    _KNOWN_TOOLTIP_ACTION_TYPES = {"showLiveChatTooltipCommand": ["tooltipRenderer"]}
    _KNOWN_POLL_ACTION_TYPES = {}
    _KNOWN_IGNORE_ACTION_TYPES = {
        # TODO add support for poll actions
        "showLiveChatActionPanelAction": [],
        "updateLiveChatPollAction": [],
        "closeLiveChatActionPanelAction": [],
    }
    _KNOWN_ACTION_TYPES = {
        **_KNOWN_ITEM_ACTION_TYPES,
        **_KNOWN_REMOVE_ACTION_TYPES,
        **_KNOWN_REPLACE_ACTION_TYPES,
        **_KNOWN_ADD_BANNER_TYPES,
        **_KNOWN_REMOVE_BANNER_TYPES,
        **_KNOWN_TOOLTIP_ACTION_TYPES,
        **_KNOWN_POLL_ACTION_TYPES,
        **_KNOWN_IGNORE_ACTION_TYPES,
    }

    _KNOWN_IGNORE_MESSAGE_TYPES = ["liveChatPlaceholderItemRenderer"]
    _KEYS_TO_IGNORE = [
        # to actually ignore
        "contextMenuAccessibility",
        "contextMenuEndpoint",
        "trackingParams",
        "accessibility",
        "dwellTimeMs",
        "empty",  # signals liveChatMembershipItemRenderer has no message body
        "contextMenuButton",
        # parsed elsewhere
        "showItemEndpoint",
        "durationSec",
        # banner parsed elsewhere
        "header",
        "contents",
        "actionId",
        # tooltipRenderer
        "dismissStrategy",
        "suggestedPosition",
        "promoConfig",
    ]

    _KNOWN_KEYS = set(
        list(YoutubeChatParser._REMAPPING.keys())
        + YoutubeChatParser._COLOUR_KEYS
        + YoutubeChatParser._STICKER_KEYS
        + _KEYS_TO_IGNORE
    )

    _KNOWN_SEEK_CONTINUATIONS = ["playerSeekContinuationData"]

    _KNOWN_CHAT_CONTINUATIONS = [
        "invalidationContinuationData",
        "timedContinuationData",
        "liveChatReplayContinuationData",
        "reloadContinuationData",
    ]

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
                cookie_jar = parse_cookie_to_morsel(cookies_str)
            except ValueError:
                self.logger.error("Invalid Netscape Cookie File, ignoring cookies!")

            for name, cookie in cookie_jar.items():
                self.session.cookie_jar.update_cookies({name: cookie})
            self.logger.info("Loaded %d cookies", len(cookie_jar))

    async def close(self):
        if self.session and not self.session.closed:
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
            morsel_sapis.set("SAPISID", sapisid_cookie, url_quote(sapisid_cookie))
            morsel_sapis["secure"] = True
            morsel_sapis["expires"] = parse_expiry_as_date(time_now + 3600)
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

    def _update_headers(self, headers: Dict[str, str]):
        self.session.headers.update(headers)

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

    async def _fetch_chat(self, continuation_url: str, context: Dict[str, Any]):
        async with self.session.post(continuation_url, json=context) as resp:
            try:
                json_data = await resp.json()
                return json_data
            except ValueError:
                self.logger.error("Failed to parse JSON response")
                return

    def _create_offset_ms(self, start_at: int):
        if not start_at:
            return None
        current_time = pendulum.now("UTC").timestamp()
        delta_time = current_time - (start_at / 1000)
        if delta_time < 0:
            return None
        return delta_time

    async def _iterate_chat(self, chat_info: ChatDetails, start_at: Optional[int] = None):
        if len(chat_info.continuations) < 2:
            raise RuntimeError("Initial continuation information could not be found")

        # Get all messages from the chat
        status = chat_info.status
        start_time = end_time = offset = None
        if start_at:
            start_time = self._create_offset_ms(start_at)
        offset_milliseconds = (start_time * 1000) if isinstance(start_time, (float, int)) else None
        continuation = chat_info.continuations[1]
        self.logger.debug(f"Getting {continuation.title} chat.")

        is_replay = status == "past"
        api_type = "live_chat"
        if is_replay:
            api_type += "_replay"

        init_page = f"https://www.youtube.com/{api_type}?continuation={continuation.continuation}"
        api_key = chat_info.cfg.get("INNERTUBE_API_KEY")
        continuation_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_{api_type}?key={api_key}"

        innertube_context = chat_info.cfg.get("INNERTUBE_CONTEXT") or {}
        session_header = self._generate_ytcfg_header(chat_info.cfg)
        self._update_headers(session_header)

        message_count = 0
        first_time = True
        click_tracking_params = None

        while True:
            continuation_params = {"context": innertube_context, "continuation": continuation}

            if first_time:
                first_run, _ = await self._session_get(init_page)
                yt_info = parse_initial_data(first_run)
            else:
                if is_replay and offset_milliseconds is not None:
                    continuation_params["currentPlayerState"] = {"playerOffsetMs": str(offset_milliseconds)}
                if click_tracking_params:
                    continuation_params["context"]["clickTracking"] = {
                        "clickTrackingParams": click_tracking_params,
                    }
                yt_info = await self._fetch_chat(continuation_url, continuation_params)

            info = complex_walk(yt_info, "continuationContents.liveChatContinuation")
            if not info:
                self.logger.debug(f"No chat information found: {info}")
                return

            actions = info.get("actions", [])
            if actions:
                for action in actions:
                    data = {}

                    # if it is a replay chat item action, must re-base it
                    replay_chat_item_action = action.get("replayChatItemAction")
                    if replay_chat_item_action:
                        offset_time = replay_chat_item_action.get("videoOffsetTimeMsec")
                        if offset_time:
                            data["time_in_seconds"] = float(offset_time) / 1000

                        action = replay_chat_item_action["actions"][0]

                    action.pop("clickTrackingParams", None)
                    original_action_type = try_get_first_key(action)

                    data["action_type"] = camel_case_split(
                        remove_suffixes(original_action_type, ("Action", "Command"))
                    )

                    original_message_type = None
                    original_item = {}

                    # We now parse the info and get the message
                    # type based on the type of action
                    if original_action_type in self._KNOWN_ITEM_ACTION_TYPES:
                        original_item = complex_walk(action, f"{original_action_type}.item")

                        original_message_type = try_get_first_key(original_item)
                        data = YoutubeChatParser.parse_item(original_item, data, offset)
                    elif original_action_type in self._KNOWN_REMOVE_ACTION_TYPES:
                        original_item = action
                        if original_action_type == "markChatItemAsDeletedAction":
                            original_message_type = "deletedMessage"
                        else:  # markChatItemsByAuthorAsDeletedAction
                            original_message_type = "banUser"

                        data = YoutubeChatParser.parse_item(original_item, data, offset)
                    elif original_action_type in self._KNOWN_REPLACE_ACTION_TYPES:
                        original_item = complex_walk(action, f"{original_action_type}.replacementItem")

                        original_message_type = try_get_first_key(original_item)
                        data = YoutubeChatParser.parse_item(original_item, data, offset)
                    elif original_action_type in self._KNOWN_TOOLTIP_ACTION_TYPES:
                        original_item = complex_walk(action, f"{original_action_type}.tooltip")

                        original_message_type = try_get_first_key(original_item)
                        data = YoutubeChatParser.parse_item(original_item, data, offset)
                    elif original_action_type in self._KNOWN_ADD_BANNER_TYPES:
                        original_item = complex_walk(action, f"{original_action_type}.bannerRenderer")

                        if original_item:
                            original_message_type = try_get_first_key(original_item)

                            header = original_item[original_message_type].get("header")
                            parsed_header = YoutubeChatParser.parse_item(header, offset=offset)
                            header_message = parsed_header.get("message")

                            contents = original_item[original_message_type].get("contents")
                            parsed_contents = YoutubeChatParser.parse_item(contents, offset=offset)

                            data.update(parsed_header)
                            data.update(parsed_contents)
                            data["header_message"] = header_message
                        else:
                            self.logger.debug(
                                "No bannerRenderer item\n"
                                f"Action type: {original_action_type}\n"
                                f"Action: {action}\n"
                                f"Parsed data: {data}"
                            )
                    elif original_action_type in self._KNOWN_REMOVE_BANNER_TYPES:
                        original_item = action
                        original_message_type = "removeBanner"
                        data = self._parse_item(original_item, data, offset)
                    elif original_action_type in self._KNOWN_IGNORE_ACTION_TYPES:
                        continue
                    else:
                        self.logger.debug(f"Unknown action: {original_action_type}\n{action}\n{data}")

                    test_for_missing_keys = original_item.get(original_message_type, {}).keys()
                    missing_keys = test_for_missing_keys - self._KNOWN_KEYS

                    if not data:
                        self.logger.debug(
                            f"Parse of action returned empty results: {original_action_type}\n{action}"
                        )

                    if missing_keys:
                        self.logger.debug(
                            f"Missing keys found: {missing_keys}\n"
                            f"Message type: {original_message_type}\n"
                            f"Action type: {original_action_type}\n"
                            f"Action: {action}\n"
                            f"Parsed data: {data}"
                        )

                    if original_message_type:
                        new_index = remove_prefixes(original_message_type, "liveChat")
                        new_index = remove_suffixes(new_index, "Renderer")
                        data["message_type"] = camel_case_split(new_index)

                        # TODO add option to keep placeholder items
                        if original_message_type in self._KNOWN_IGNORE_MESSAGE_TYPES:
                            continue
                            # skip placeholder items
                        elif original_message_type not in self._KNOWN_ACTION_TYPES[original_action_type]:
                            self.logger.debug(
                                f'Unknown message type "{original_message_type}"\n'
                                f"New message type: {data['message_type']}\n"
                                f"Action: {action}\n"
                                f"Parsed data: {data}"
                            )

                    else:
                        # Ignore
                        self.logger.debug(
                            f"No message type found for action: {original_action_type}\n"
                            f"Action: {action}\n"
                            f"Parsed data: {data}"
                        )
                        continue

                    if is_replay:
                        # assume message is at beginning if it does not have a time component
                        time_in_seconds = data.get("time_in_seconds", 0) + (offset or 0)

                        before_start = start_time is not None and time_in_seconds < start_time
                        after_end = end_time is not None and time_in_seconds > end_time

                        if first_time and before_start:
                            continue  # first time and invalid start time
                        elif before_start or after_end:
                            return  # while actually searching, if time is invalid

                    message_count += 1
                    yield ChatEvent.data, data

                self.logger.debug(f"Total number of messages: {message_count}")
            elif is_replay:
                break
            else:
                self.logger.debug("No actions to process.")

            no_continuation = True

            for cont in info.get("continuations", []):
                continuation_key = try_get_first_key(cont)
                continuation_info = cont[continuation_key]

                self.logger.debug(f"Continuation info: {continuation_info}")

                if continuation_key in self._KNOWN_CHAT_CONTINUATIONS:
                    # set new chat continuation
                    # overwrite if there is continuation data
                    continuation = continuation_info.get("continuation")
                    click_tracking_params = continuation_info.get(
                        "clickTrackingParams"
                    ) or continuation_info.get("trackingParams")
                    # there is a chat continuation
                    no_continuation = False
                elif continuation_key in self._KNOWN_SEEK_CONTINUATIONS:
                    pass
                else:
                    self.logger.debug(f"Unknown continuation: {continuation_key}\n{cont}")

                sleep_duration = continuation_info.get("timeoutMs")
                yield ChatEvent.wait, sleep_duration
                if sleep_duration:
                    sleep_duration = max(min(sleep_duration, 8000), 0)

                    self.logger.debug(f"Sleeping for {sleep_duration}ms")
                    await asyncio.sleep(sleep_duration / 1000)

            if no_continuation:
                break

            if first_time:
                first_time = False

    async def _validate_result(self, chat_info: ChatDetails):
        if not chat_info.continuations:
            playability_status = chat_info.player_response.get("playabilityStatus", {})
            error_screen = playability_status.get("errorScreen") or {}
            if error_screen:
                error_reasons = {
                    "reason": "",
                    "subreason": "",
                }
                try:
                    err_info = next(iter(error_screen.values()))
                except Exception:
                    err_info = {}

                for error_reason in error_reasons:
                    text = err_info.get(error_reason) or {}
                    error_reasons[error_reason] = (
                        text.get("simpleText")
                        or YoutubeChatParser.parse_runs(text, False).message
                        or err_info.pop("offerDescription", "")
                        or playability_status.get(error_reason)
                        or ""
                    )

                error_message = ""
                for error_reason in error_reasons:
                    if error_reasons[error_reason]:
                        if isinstance(error_reasons[error_reason], str):
                            error_message += f" {error_reasons[error_reason].rstrip('.')}."
                        else:
                            error_message += str(error_reasons[error_reason])

                error_message = error_message.strip()
                status = playability_status.get("status")
                if status == "ERROR":
                    raise VideoUnavailable(error_message)
                elif status == "LOGIN_REQUIRED":
                    raise LoginRequired(error_message)
                elif status == "UNPLAYABLE":
                    raise VideoUnplayable(error_message)
                else:
                    self.logger.debug(f"Unknown playability status: {status}. {playability_status}")
                    error_message = f"{status}: {error_message}"
                    raise VideoUnavailable(error_message)

            popup_info = complex_walk(
                chat_info.initial_data,
                "onResponseReceivedActions.0.openPopupAction.popup.confirmDialogRenderer",
            )
            if popup_info:
                error_message = complex_walk(popup_info, "title.simpleText")
                dialog_messages = complex_walk(popup_info, "dialogMessages") or []
                error_message += ". " + " ".join(map(lambda x: x.get("simpleText"), dialog_messages))
                raise VideoUnavailable(error_message)
            elif not chat_info.initial_data.get("contents"):
                raise VideoUnavailable("Unable to find the initial video contents")
            else:
                error_runs = complex_walk(
                    chat_info.initial_data,
                    "contents.twoColumnWatchNextResults.conversationBar.conversationBarRenderer.availabilityMessage.messageRenderer.text",  # noqa
                )
                error_message = (
                    YoutubeChatParser.parse_runs(error_runs, False).message
                    if error_runs
                    else "Video does not have a chat replay."
                )

                if "disabled" in error_message:
                    raise ChatDisabled(error_message)
                else:
                    raise NoChatReplay(error_message)

    async def _actually_start(
        self, chat_info: ChatDetails, writer: JSONWriter, start_at: Optional[int] = None
    ):
        try:
            async for event, chat in self._iterate_chat(chat_info, start_at):
                if event == ChatEvent.data:
                    await writer.write(chat)
                elif event == ChatEvent.wait:
                    self.logger.debug(f"Sleeping for {chat}ms")
                    await writer.flush()
            return True, False
        except (VideoUnplayable, VideoUnavailable) as e:
            self.logger.error("Unable to get the video, might be unavailable?", exc_info=e)
            return False, False
        except ChatDisabled:
            self.logger.error("Chat is disabled, checking if we should retry again...")
            if chat_info.status == "upcoming":
                return False, True
            return False, False
        except LoginRequired:
            self.logger.error("Login required, unable to get the video. (Provide cookies!)")
            return False, False
        except NoChatReplay:
            self.logger.error("No chat replay available.")
            return False, False
        except asyncio.CancelledError:
            self.logger.debug("Cancelled")
            return False, False

    async def start(self, writer: JSONWriter, start_at: Optional[int] = None):
        if self.session is None:
            await self.create()
        chat_info = await self._get_yt_initial_data(self.video_id)
        if chat_info is None:
            self.logger.debug("Unable to get the initial data.")
            return
        try:
            await self._validate_result(chat_info)
        except VideoUnplayable as exc:
            self.logger.error(f"Video unplayable: {exc}")
            return
        except LoginRequired:
            self.logger.error("You need to be logged in to access this chat/video!")
            return
        except VideoUnavailable as exc:
            self.logger.error(f"Video unavailable: {exc}")
            return
        except ChatDisabled as exc:
            self.logger.error(f"Chat disabled: {exc}")
            return
        except NoChatReplay as exc:
            self.logger.error(f"No chat replay available: {exc}")
            return

        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            success, retry = await self._actually_start(chat_info, writer, start_at)
            if success or not retry:
                self.logger.debug(f"Breaking the loop, success: {success}, retry: {retry}")
                break
            self.logger.debug("Retrying chat downloader in 60s...")
            await asyncio.sleep(60.0)
            chat_info = await self._get_yt_initial_data(self.video_id)
            if chat_info is None:
                self.logger.debug("Unable to get the initial data while retrying...")
                return
            retry_count += 1

        await writer.flush()
