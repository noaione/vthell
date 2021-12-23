import re
from dataclasses import dataclass, field
from http.cookies import Morsel
from typing import Any, Dict, List, Literal, Union
from urllib.parse import quote as url_quote

import orjson

INITIAL_BOUNDARY_RE = r"\s*(?:var\s+meta|</script|\n)"

INITIAL_DATA_RE = (
    r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;' + INITIAL_BOUNDARY_RE
)
INITIAL_PLAYER_RESPONSE_RE = r"ytInitialPlayerResponse\s*=\s*({.+?})\s*;" + INITIAL_BOUNDARY_RE
CFG_RE = r"ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;"

__all__ = ("ContinuationInfo", "ChatDetails", "parse_netscape_cookie_to_morsel", "parse_youtube_video_data")


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

    # Extra
    initial_data: Dict[str, Any] = field(repr=False)
    player_response: Dict[str, Any] = field(repr=False)
    cfg: Dict[str, Any] = field(repr=False)


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
        cookie["expires"] = expiration
        cookie["httponly"] = True
        netscape_cookies[name] = cookie

    return netscape_cookies


def parse_youtube_video_data(html_string: str):
    initial_data = parse_initial_data(html_string)
    yt_config = parse_yt_config(html_string)
    player_resp = parse_player_response(html_string)

    # Live streaming details
    video_details = player_resp.get("videoDetails", {})

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
            "contents.twoColumnWatchNextResults.conversationBar.liveChatRenderer.header.liveChatHeaderRenderer.viewSelector.sortFilterSubMenuRenderer.subMenuItems",  # noqa: E501
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

    return ChatDetails(
        video_id,
        title,
        channel_id,
        video_status,
        video_type,
        continuations,
        initial_data,
        player_resp,
        yt_config,
    )
