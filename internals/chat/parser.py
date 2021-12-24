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

import re
from dataclasses import dataclass, field
from http.cookies import Morsel
from typing import Any, Dict, List, Literal, Optional, Union
from urllib.parse import parse_qsl
from urllib.parse import quote as url_quote
from urllib.parse import urlsplit

import orjson

from internals.chat.remapper import Remapper as r
from internals.chat.utils import (
    arbg_int_to_rgba,
    camel_case_split,
    float_or_none,
    int_or_none,
    parse_expiry_as_date,
    parse_iso8601,
    rgba_to_hex,
    seconds_to_time,
    time_to_seconds,
    try_get_first_key,
)

INITIAL_BOUNDARY_RE = r"\s*(?:var\s+meta|</script|\n)"

INITIAL_DATA_RE = (
    r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;' + INITIAL_BOUNDARY_RE
)
INITIAL_PLAYER_RESPONSE_RE = r"ytInitialPlayerResponse\s*=\s*({.+?})\s*;" + INITIAL_BOUNDARY_RE
CFG_RE = r"ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;"

__all__ = (
    "ChatDetails",
    "MessageEmoji",
    "ChatRuns",
    "Image",
    "get_indexed",
    "complex_walk",
    "parse_initial_data",
    "parse_yt_config",
    "parse_player_response",
    "parse_youtube_video_data",
    "parse_netscape_cookie_to_morsel",
    "YoutubeChatParser",
)


@dataclass
class ContinuationInfo:
    title: str
    continuation: str
    selected: bool


@dataclass
class ChatDetails:
    id: str
    title: str
    channel_id: str
    status: Literal["live", "upcoming", "past"]
    type: Literal["premiere", "video"]
    continuations: List[ContinuationInfo]

    start_time: Optional[int] = field(default=None)
    end_time: Optional[int] = field(default=None)
    duration: Optional[int] = field(default=None)

    # Extra
    initial_data: Dict[str, Any] = field(repr=False, default_factory=dict)
    player_response: Dict[str, Any] = field(repr=False, default_factory=dict)
    cfg: Dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass
class MessageEmoji:
    id: str
    name: str
    shortcuts: List[str]
    search_terms: List[str]
    images: Dict[str, str]
    is_custom_emoji: bool

    def json(self):
        return {
            "id": self.id,
            "name": self.name,
            "shortcuts": self.shortcuts,
            "search_terms": self.search_terms,
            "images": self.images,
            "is_custom_emoji": self.is_custom_emoji,
        }


@dataclass
class ChatRuns:
    message: str
    emotes: List[MessageEmoji] = field(default_factory=list)

    def json(self):
        base = {"message": self.message}
        if self.emotes:
            base["emotes"] = [emote.json() for emote in self.emotes]
        return base


@dataclass
class Image:
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    image_id: Optional[str] = None

    def __post_init__(self):
        if self.url.startswith("//"):
            self.url = "https:" + self.url

        if self.width and self.height and not self.image_id:
            self.image_id = f"{self.width}x{self.height}"

    def json(self):
        return {
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "id": self.image_id,
        }


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


def parse_initial_data(html_string: str):
    """
    Parses the initial data from the html string.
    :param html_string: The html string to parse.
    :return: The initial data.
    """
    initial_data_match = re.search(INITIAL_DATA_RE, html_string)
    if initial_data_match:
        return orjson.loads(initial_data_match.group(1))
    return None


def parse_yt_config(html_string: str):
    """
    Parses the yt config from the html string.
    :param html_string: The html string to parse.
    :return: The yt config.
    """
    cfg_match = re.search(CFG_RE, html_string)
    if cfg_match:
        return orjson.loads(cfg_match.group(1))
    return None


def parse_player_response(html_string: str):
    """
    Parses the player response from the html string.
    :param html_string: The html string to parse.
    :return: The player response.
    """
    player_response_match = re.search(INITIAL_PLAYER_RESPONSE_RE, html_string)
    if player_response_match:
        return orjson.loads(player_response_match.group(1))
    return None


def parse_netscape_cookie_to_morsel(cookie_content: str):
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


def parse_youtube_video_data(html_string: str):
    initial_data = parse_initial_data(html_string)
    yt_config = parse_yt_config(html_string)
    player_resp = parse_player_response(html_string)

    # Live streaming details
    video_details = player_resp.get("videoDetails", {})
    player_renderer = complex_walk(player_resp, "microformat.playerMicroformatRenderer") or {}
    live_details = player_renderer.get("liveBroadcastDetails") or {}

    streaming_data = player_resp.get("streamingData") or {}
    first_format = (
        complex_walk(streaming_data, "adaptiveFormats.0") or complex_walk(streaming_data, "formats.0") or {}
    )

    title = video_details.get("title")
    channel_id = video_details.get("channelId")
    video_id = video_details.get("videoId")

    if not video_details.get("isLiveContent"):
        video_type = "premiere"
    else:
        video_type = "video"

    # live, upcoming or past
    if video_details.get("isLive") or video_details.get("isLiveNow"):
        video_status = "live"
    elif video_details.get("isUpcoming"):
        video_status = "upcoming"
    else:
        video_status = "past"

    # Continuation chat
    sub_menu_items = (
        complex_walk(
            initial_data,
            "contents.twoColumnWatchNextResults.conversationBar.liveChatRenderer.header.liveChatHeaderRenderer.viewSelector.sortFilterSubMenuRenderer.subMenuItems",  # noqa
        )
        or {}
    )

    continuations: List[ContinuationInfo] = []
    for item in sub_menu_items:
        chat_title = item["title"]
        selected = item.get("selected", False)
        continuation = complex_walk(item, "continuation.reloadContinuationData.continuation")
        if not continuation:
            continue
        continuations.append(ContinuationInfo(chat_title, continuation, selected))

    start_timestamp = parse_iso8601(live_details.get("startTimestamp"))
    end_timestamp = parse_iso8601(live_details.get("endTimestamp"))

    duration = (
        float_or_none(first_format.get("approxDurationMs", 0)) / 1e3
        or float_or_none(video_details.get("lengthSeconds"))
        or float_or_none(player_renderer.get("lengthSeconds"))
    )

    if not duration and start_timestamp and end_timestamp:
        duration = (end_timestamp - start_timestamp) / 1e6

    return ChatDetails(
        video_id,
        title,
        channel_id,
        video_status,
        video_type,
        continuations,
        start_timestamp,
        end_timestamp,
        duration,
        initial_data,
        player_resp,
        yt_config,
    )


class YoutubeChatParser:
    def __init__(self) -> None:
        pass

    _CURRENCY_SYMBOLS = {
        "$": "USD",
        "A$": "AUD",
        "CA$": "CAD",
        "HK$": "HKD",
        "MX$": "MXN",
        "NT$": "TWD",
        "NZ$": "NZD",
        "R$": "BRL",
        "£": "GBP",
        "€": "EUR",
        "₹": "INR",
        "₪": "ILS",
        "₱": "PHP",
        "₩": "KRW",
        "￦": "KRW",
        "¥": "JPY",
        "￥": "JPY",
    }

    _STICKER_KEYS = [
        # to actually ignore
        "stickerDisplayWidth",
        "stickerDisplayHeight",  # ignore
        # parsed elsewhere
        "sticker",
    ]

    @staticmethod
    def parse_youtube_navigation_link(text: str):
        if text.startswith(("/redirect", "https://www.youtube.com/redirect")):  # is a redirect link
            info = dict(parse_qsl(urlsplit(text).query))
            return info.get("q") or ""
        elif text.startswith("//"):
            return "https:" + text
        elif text.startswith("/"):  # is a youtube link e.g. '/watch','/results'
            return "https://www.youtube.com" + text
        else:  # is a normal link
            return text

    @staticmethod
    def parse_navigation_endpoint(navigation_endpoint: dict, default_text: str = ""):
        try:
            return YoutubeChatParser.parse_youtube_navigation_link(
                navigation_endpoint["commandMetadata"]["webCommandMetadata"]["url"]
            )
        except Exception:
            return default_text

    @staticmethod
    def get_source_image_url(url: str):
        index = url.find("=")
        if index >= 0:
            return url[0 : url.index("=")]
        else:
            return url

    @staticmethod
    def parse_youtube_thumbnail(item: Union[list, dict]):
        # sometimes thumbnails come as a list
        if isinstance(item, list):
            item = item[0]  # rebase

        thumbnails = item.get("thumbnails") or []
        final = list(map(lambda x: Image(**x).json(), thumbnails))

        if len(final) > 0:
            final.insert(
                0, Image(YoutubeChatParser.get_source_image_url(final[0]["url"]), image_id="source").json()
            )

        return final

    @staticmethod
    def parse_runs(run_info: dict, parse_links: bool = True):
        """Reads and parses YouTube formatted messages (i.e. runs)."""

        message_info = ChatRuns("")

        if not isinstance(run_info, dict):
            return message_info

        message_emotes: Dict[str, MessageEmoji] = {}

        runs = run_info.get("runs", [])
        for run in runs:
            if "text" in run:
                if parse_links and "navigationEndpoint" in run:
                    # is a link and must parse
                    # if something fails, use default text
                    message_info.message += YoutubeChatParser.parse_navigation_endpoint(
                        run["navigationEndpoint"], run["text"]
                    )
                else:
                    # is a normal message
                    message_info.message += run["text"]
            elif "emoji" in run:
                emoji = run["emoji"]
                emoji_id = emoji.get("emojiId")
                name = complex_walk(emoji, "shortcuts.0")

                if name:
                    if emoji_id and emoji_id not in message_emotes:
                        emoji_msg = MessageEmoji(
                            emoji_id,
                            name,
                            emoji.get("shortcuts"),
                            emoji.get("searchTerms"),
                            YoutubeChatParser.parse_youtube_thumbnail(emoji.get("image", {})),
                            emoji.get("isCustomEmoji", False),
                        )
                        message_emotes[emoji_id] = emoji_msg
                    message_info.message += name
            else:
                # unknown run
                message_info.message += str(run)

        if message_emotes:
            message_info.emotes = list(message_emotes.values())

        return message_info

    @staticmethod
    def parse_action_button(item):
        endpoint = complex_walk(item, "buttonRenderer.navigationEndpoint")

        return {
            "url": YoutubeChatParser.parse_navigation_endpoint(endpoint) if endpoint else "",
            "text": complex_walk(item, "buttonRenderer.text.simpleText") or "",
        }

    @staticmethod
    def parse_currency(item):
        mixed_text = item.get("simpleText") or str(item)

        info = re.split(r"([\d,\.]+)", mixed_text)
        if len(info) >= 2:  # Correct parse
            currency_symbol = info[0].strip()
            currency_code = YoutubeChatParser._CURRENCY_SYMBOLS.get(currency_symbol, currency_symbol)
            amount = float(info[1].replace(",", ""))

        else:  # Unable to get info
            amount = float(re.sub(r"[^\d\.]+", "", mixed_text))
            currency_symbol = currency_code = None

        return {
            "text": mixed_text,
            "amount": amount,
            "currency": currency_code,  # ISO_4217
            "currency_symbol": currency_symbol,
        }

    @staticmethod
    def _move_to_dict(
        info: dict, dict_name: str, replace_key: str = None, create_when_empty: bool = False, *info_keys
    ):
        """
        Move all items with keys that contain some text to a separate dictionary.
        These keys are modifed by removing some text.
        """
        if replace_key is None:
            replace_key = dict_name + "_"

        new_dict = {}

        for key in (info_keys or info or {}).copy():
            if replace_key in key:
                info_item = info.pop(key, None)
                new_key = key.replace(replace_key, "")

                # set it if it contains info
                if info_item not in (None, [], {}):
                    new_dict[new_key] = info_item

        if dict_name in info:
            info[dict_name].update(new_dict)
        elif create_when_empty or new_dict != {}:  # dict_name not in info
            info[dict_name] = new_dict

        return new_dict

    @staticmethod
    def parse_item(item: dict, info: Optional[dict] = None, offset: int = 0):
        if info is None:
            info = {}
        # info is starting point
        item_index = try_get_first_key(item)
        item_info = item.get(item_index)

        if not item_info:
            return info

        for key in item_info:
            r.remap(info, YoutubeChatParser._REMAPPING, key, item_info[key])

        # check for colour information
        for colour_key in YoutubeChatParser._COLOUR_KEYS:
            if colour_key in item_info:  # if item has colour information
                rgba_colour = arbg_int_to_rgba(item_info[colour_key])
                hex_colour = rgba_to_hex(rgba_colour)
                new_key = camel_case_split(colour_key.replace("Color", "Colour"))
                info[new_key] = hex_colour

        item_endpoint = item_info.get("showItemEndpoint")
        if item_endpoint:  # has additional information
            renderer = complex_walk(item_endpoint, "showLiveChatItemEndpoint.renderer")

            if renderer:
                info.update(YoutubeChatParser.parse_item(renderer, offset=offset))

        YoutubeChatParser._move_to_dict(info, "author")

        # TODO determine if youtube glitch has occurred
        # round(time_in_seconds/timestamp) == 1
        time_in_seconds = info.get("time_in_seconds")
        time_text = info.get("time_text")

        if time_in_seconds is not None:

            if time_text is not None:
                # All information was provided, check if time_in_seconds is <= 0
                # For some reason, YouTube sets the video offset to 0 if the message
                # was sent before the stream started. This fixes that:
                if time_in_seconds <= 0:
                    info["time_in_seconds"] = time_to_seconds(time_text)
            else:
                # recreate time text from time in seconds
                info["time_text"] = seconds_to_time(time_in_seconds)

        elif time_text is not None:  # doesn't have time in seconds, but has time text
            info["time_in_seconds"] = time_to_seconds(time_text)
        else:
            pass
            # has no current video time information
            # (usually live video or a sub-item)

        # non-zero, non-null offset and has time_in_seconds info
        if offset and "time_in_seconds" in info:
            info["time_in_seconds"] -= offset
            info["time_text"] = seconds_to_time(info["time_in_seconds"])

        if "message" not in info:  # Ensure the parsed item contains the 'message' key
            info["message"] = None

        return info

    @staticmethod
    def parse_badges(badge_items):
        badges = []

        for badge in badge_items:
            to_add = {}
            parsed_badge = YoutubeChatParser.parse_item(badge)

            title = parsed_badge.pop("tooltip", None)
            if title:
                to_add["title"] = title

            icon = parsed_badge.pop("icon", None)
            if icon:
                to_add["icon_name"] = icon.lower()

            badge_icons = parsed_badge.pop("badge_icons", None)
            if badge_icons:
                to_add["icons"] = []

                url = None
                for icon in badge_icons:
                    url = icon.get("url")
                    if url:
                        matches = re.search(r"=s(\d+)", url)
                        if matches:
                            size = int(matches.group(1))
                            to_add["icons"].append(Image(url, size, size).json())
                if url:
                    to_add["icons"].insert(
                        0, Image(YoutubeChatParser.get_source_image_url(url), image_id="source").json()
                    )

            badges.append(to_add)

            # if 'member'
            # remove the tooltip afterwards
            # print(badges)
        return badges

    @staticmethod
    def get_simple_text(item):
        return item.get("simpleText")

    @staticmethod
    def parse_text(info):
        return YoutubeChatParser.parse_runs(info).message or YoutubeChatParser.get_simple_text(info)

    @staticmethod
    def parse_runs_json(info):
        return YoutubeChatParser.parse_runs(info).json()

    @staticmethod
    def timestamp_micro_to_mili(timestamp_micro):
        timestamp_micro = int_or_none(timestamp_micro)
        if timestamp_micro is not None:
            return timestamp_micro / 1000
        return None

    _REMAPPING = {
        "id": "message_id",
        "authorExternalChannelId": "author_id",
        "authorName": r("author_name", get_simple_text),
        # TODO author_display_name
        "purchaseAmountText": r("money", parse_currency),
        "message": r(None, parse_runs_json, True),
        "timestampText": r("time_text", get_simple_text),
        "timestampUsec": r("timestamp", timestamp_micro_to_mili),
        "authorPhoto": r("author_images", parse_youtube_thumbnail),
        "tooltip": "tooltip",
        "icon": r("icon", lambda x: x.get("iconType")),
        "authorBadges": r("author_badges", parse_badges),
        # stickers
        "sticker": r("sticker_images", parse_youtube_thumbnail),
        # ticker_paid_message_item
        "fullDurationSec": r("ticker_duration", int_or_none),
        "amount": r("money", parse_currency),
        # ticker_sponsor_item
        "detailText": r(None, parse_runs_json, True),
        "customThumbnail": r("badge_icons", parse_youtube_thumbnail),
        # membership_item
        "headerPrimaryText": r("header_primary_text", parse_text),
        "headerSubtext": r("header_secondary_text", parse_text),
        "sponsorPhoto": r("sponsor_icons", parse_youtube_thumbnail),
        # ticker_paid_sticker_item
        "tickerThumbnails": r("ticker_icons", parse_youtube_thumbnail),
        # deleted messages
        "deletedStateMessage": r(None, parse_runs_json, True),
        "targetItemId": "target_message_id",
        "externalChannelId": "author_id",
        # action buttons
        "actionButton": r("action", parse_action_button),
        # addBannerToLiveChatCommand
        "text": r(None, parse_runs_json, True),
        "viewerIsCreator": "viewer_is_creator",
        "targetId": "target_message_id",
        "isStackable": "is_stackable",
        "backgroundType": "background_type",
        # removeBannerForLiveChatCommand
        "targetActionId": "target_message_id",
        # donation_announcement
        "subtext": r(None, parse_runs_json, True),
        # tooltip
        "detailsText": r(None, parse_runs_json, True),
    }

    _COLOUR_KEYS = [
        # paid_message
        "authorNameTextColor",
        "timestampColor",
        "bodyBackgroundColor",
        "headerTextColor",
        "headerBackgroundColor",
        "bodyTextColor",
        # paid_sticker
        "backgroundColor",
        "moneyChipTextColor",
        "moneyChipBackgroundColor",
        # ticker_paid_message_item
        "startBackgroundColor",
        "amountTextColor",
        "endBackgroundColor",
        # ticker_sponsor_item
        "detailTextColor",
    ]
