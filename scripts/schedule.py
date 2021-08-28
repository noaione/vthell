import json
import logging
import os
import re
import sys
from datetime import datetime
from os.path import join as pjoin

import requests

BASE_VTHELL_PATH = (
    "/media/sdac/mizore/vthell/"  # Absoule path to vthell folder
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
    fn = fn.sub(EMOJI_PATTERN, "_", fn)
    return fn


logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(
            pjoin(BASE_VTHELL_PATH, "nvthell.log"), "a", "utf-8"
        )
    ],
    format="%(asctime)s %(name)-1s -- [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
vtlog = logging.getLogger("vtschedule")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)


def to_utc9(t: datetime) -> datetime:
    utc = t.timestamp() + (9 * 60 * 60)
    dtn = datetime.fromtimestamp(utc)
    return dtn


def reset_logger(r=True):
    if r:
        vtlog.removeHandler(console)
    formatter1 = logging.Formatter("[%(levelname)s]: %(message)s")
    console.setFormatter(formatter1)
    vtlog.addHandler(console)


def set_logger(vt, ids):
    formatterany = logging.Formatter(
        "[%(levelname)s]: ({v}) {a}: %(message)s".format(v=vt, a=ids)
    )
    vtlog.removeHandler(console)
    console.setFormatter(formatterany)
    vtlog.addHandler(console)


reset_logger(False)


class BilibiliScheduler:

    BASE_API = "https://api.live.bilibili.com/xlive/web-room/v1"
    BASE_API += "/index/getInfoByRoom?room_id={}"

    def __init__(self, url):
        self.id = None
        self.streamweb = "BiliBili"
        self.rgx1 = re.compile(r"http(?:s|)\:\/\/live\.bilibili\.com\/")
        self.__fetch_id(url)

    def __fetch_id(self, url):
        self.id = re.sub(self.rgx1, "", url)
        set_logger("BiliBili", self.id)

    def process(self):
        s = requests.get(self.BASE_API.format(self.id))
        if s.status_code != 200:
            vtlog.error("Failed fetching to the API, please try again later.")
            sys.exit(1)

        res = s.json()
        print(json.dumps(res, indent=2))

    def dumps(self):
        return {}


class YoutubeScheduler:

    BASE_API = "https://www.googleapis.com/youtube/v3/"
    BASE_API += "videos?id={}&key={}"
    BASE_API += (
        "&part=snippet%2Cstatus%2CliveStreamingDetails%2CcontentDetails"
    )
    BASE_YT_WATCH = "https://www.youtube.com/watch?v="

    def __init__(self, url):
        self.id = None
        self.rgx1 = re.compile(
            r"http(?:s|)\:\/\/(?:www.|)youtu(?:.be|be\.com)\/"
        )
        self.rgx2 = re.compile(r"watch\?v\=")
        self.streamweb = "YouTube"
        self.member_stream = False
        self.API_KEY = None
        self.__fetch_id(url)
        self.__fetch_apikey()

    def __fetch_id(self, url):
        if "ms." in url:
            url = url.replace("ms.", "")
            self.member_stream = True
        self.id = re.sub(self.rgx1, "", url)
        self.id = re.sub(self.rgx2, "", self.id)
        set_logger("YouTube", self.id)

    def __fetch_apikey(self):
        self.API_KEY = os.getenv("VTHELL_YT_API_KEY", "")
        if not self.API_KEY:
            vtlog.error("Please provide VTHELL_YT_API_KEY to the environment.")
            sys.exit(1)

    def process(self):
        vtlog.info("Fetching to API...")
        if self.member_stream:
            vtlog.info("Detected as Member-Only Stream.")
        s = requests.get(self.BASE_API.format(self.id, self.API_KEY))
        if s.status_code != 200:
            vtlog.error("Failed fetching to the API, please try again later.")
            sys.exit(1)

        res = s.json()

        vtlog.info("Processing data...")
        snippets = res["items"][0]["snippet"]
        livedetails = res["items"][0]["liveStreamingDetails"]

        if "actualStartTime" in livedetails:
            start_time = livedetails["actualStartTime"]
        else:
            start_time = livedetails["scheduledStartTime"]
        title = snippets["title"]
        self.streamer = snippets["channelId"]

        try:
            dts = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            dts = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
        self.start_time = dts.timestamp()
        dtymd = to_utc9(dts).strftime("[%Y.%m.%d]")
        dtymd = dtymd[:-1] + ".{}]".format(self.id)
        self.filename = "{} {}".format(dtymd, title)
        self.filename = secure_filename(self.filename)

    def dumps(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "startTime": self.start_time - 60,
            "streamer": self.streamer,
            "streamUrl": self.BASE_YT_WATCH + self.id,
            "type": "youtube",
            "memberOnly": self.member_stream,
            "isDownloading": False,
            "isDownloaded": False,
            "isPaused": False,
            "firstRun": True,
        }


def determine_url(url: str):
    if "bilibili" in url:
        return BilibiliScheduler
    if "youtube" in url or "youtu.be" in url:
        return YoutubeScheduler
    return None


try:
    batched_urls = sys.argv[1:]
except IndexError:
    vtlog.error("No URL provided, exiting...")
    exit(1)

if not batched_urls:
    vtlog.error("No URL provided, exiting...")
    exit(1)

vtlog.info("Total url provided: {}".format(len(batched_urls)))

for ninp, input_url in enumerate(batched_urls, 1):
    vtlog.info("Determining url no.{}...".format(ninp))
    Scheduler = determine_url(input_url)
    if not Scheduler:
        vtlog.error("Unknown URL: {}, continuing.".format(input_url))
        continue
    vtlog.info("Scheduling: {}".format(input_url))

    Scheduler = Scheduler(input_url)
    if Scheduler.streamweb == "BiliBili":
        vtlog.warn("BiliBili support aren't finished yet, continuing...")
        continue
    Scheduler.process()

    json_output = Scheduler.dumps()
    vtlog.info("Saving fetched data into jobs file")

    with open(
        pjoin(BASE_VTHELL_PATH, "jobs", json_output["id"] + ".json"),
        "w",
        encoding="utf-8",
    ) as fp:
        json.dump(json_output, fp, indent=2)

    vtlog.info("Scheduled!")
    reset_logger()
