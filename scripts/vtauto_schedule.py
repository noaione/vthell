import glob
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from os.path import basename as pbase
from os.path import join as pjoin
from os.path import splitext as psplit

import pytz
import requests
from discord_webhook import DiscordEmbed, DiscordWebhook

"""
A tools to automatically schedule upcoming streams!
Only support Hololive and Nijisanji for now
Using dragonjet (jetri.co) API Endpoint.

Please change BASE_VTHELL_PATH to your VTHell folder.
"""

BASE_VTHELL_PATH = (
    "/media/sdac/mizore/vthell/"  # Absoule path to vthell folder
)

DISCORD_WEBHOOK_URL = os.getenv("VTHELL_DISCORD_WEBHOOK", "")

"""
Set to True or False if you want it to be processed/scheduled automatically

Default:
- Enable Hololive
- Disable Nijisanji
So, it will process Hololive but skip Nijisanji completely.

There's also `ENABLE_BILIBILI` this will enable fetching to the BiliBili API
for Upcoming live data.
Set to True if you want to check it.
"""
PROCESS_HOLOLIVE = True
PROCESS_NIJISANJI = False

ENABLE_BILIBILI = True

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
vtlog = logging.getLogger("vthell_autoschedule")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)

formatter1 = logging.Formatter("[%(asctime)s] %(message)s")
console.setFormatter(formatter1)
vtlog.addHandler(console)

vtlog.info("Collecting existing jobs...")
vthell_jobs = glob.glob(pjoin(BASE_VTHELL_PATH, "jobs", "*.json"))
vthell_jobs = [psplit(pbase(job))[0] for job in vthell_jobs]


class ValidationError(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class StreamData:
    """Stream Information parser that used info like Jetri.co API
    Required schema (You can other stuff yourself.)
    {
        "id": str,
        "title": str
        "channel": str,
        "startTime": int/str
    }
    """

    BASE_YT_WATCH = "https://www.youtube.com/watch?v="
    BASE_BILI_WATCH = "https://live.bilibili.com/"

    def __init__(self, data: dict, web: str = "youtube"):
        self._st_data = data
        self._type = web
        self.__validate_schema()
        self.__parse_data()

    def __validate_schema(self):
        vtlog.debug("Validating schemas...")
        schemas = {
            "id": (str),
            "title": (str),
            "channel": (str),
            "startTime": (str, int),
        }
        self._type = self._type.lower()
        if self._type not in ("youtube", "bilibili"):
            raise ValueError(
                'Unknown "web" type, must be `youtube` or `bilibili`'
            )
        if self._type == "bilibili":
            schemas["room_id"] = (str, int)
        self._WATCH_URL = (
            self.BASE_YT_WATCH
            if self._type == "youtube"
            else self.BASE_BILI_WATCH
        )
        for key, value in schemas.items():
            if key not in self._st_data:
                raise ValidationError(
                    "Key {} doesn't exist on your input, please revalidate."
                )
            if not isinstance(self._st_data[key], value):
                if isinstance(value, tuple):
                    tn = '"' + '" or "'.join([s.__name__ for s in value]) + '"'
                else:
                    tn = value.__name__
                raise ValidationError(
                    'Key "{}" format are wrong (must be {})'.format(key, tn)
                )
        vtlog.debug("Schema valid.")

    def __secure_filename(self, fn: str):
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

    def __format_filename(self):
        ctime = self._st_data["startTime"]
        if isinstance(ctime, str):
            ctime = int(ctime)
        ctime += 9 * 60 * 60
        tsd = datetime.fromtimestamp(ctime, pytz.timezone("Asia/Tokyo"))
        ts_strf = tsd.strftime("[%Y.%m.%d")
        ts_strf = ts_strf + ".{}]".format(self.id)
        return self.__secure_filename("{} {}".format(ts_strf, self._title))

    def __parse_data(self):
        self.id = self._st_data["id"]
        self._title = self._st_data["title"]
        self._streamer = self._st_data["channel"]
        if isinstance(self._st_data["startTime"], str):
            self._st_data["startTime"] = int(self._st_data["startTime"])
        self._start_time = self._st_data["startTime"]
        self._filename = self.__format_filename()
        self.stream_url = self._WATCH_URL + self.id
        if self._type == "bilibili":
            self.stream_url = self._WATCH_URL + str(self._st_data["room_id"])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self._filename,
            "startTime": self._start_time - 60,
            "streamer": self._streamer,
            "streamUrl": self.stream_url,
            "type": self._type,
            "memberOnly": False,
            "isDownloading": False,
            "isDownloaded": False,
            "isPaused": False,
            "firstRun": True,
        }


class AutoScheduler:
    """Main filtering and request process in here."""

    def __init__(self):
        self._ignore = True

    def __is_bilibili(self, data):
        is_bili = False
        if "platform" in data and data["platform"].lower() == "bilibili":
            is_bili = True
        if "room_id" in data and isinstance(data["room_id"], int):
            is_bili = True
        return is_bili

    def __ignore_channel(self, data, channel):
        new_data = []
        channel = str(channel)
        for st in data:
            if channel == st["channel"]:
                continue
            new_data.append(st)
        return new_data

    def __ignore_word(self, data, word):
        new_data = []
        for st in data:
            if word in st["title"]:
                continue
            new_data.append(st)
        return new_data

    def __collect_word(self, data, word):
        collected = []
        for st in data:
            if word in st["title"]:
                _type = "youtube"
                if self.__is_bilibili(st):
                    _type = "bilibili"
                collected.append(StreamData(st, _type))
        return collected

    def __collect_channel(self, data, channel):
        collected = []
        channel = str(channel)
        for st in data:
            if channel == st["channel"]:
                _type = "youtube"
                if self.__is_bilibili(st):
                    _type = "bilibili"
                collected.append(StreamData(st, _type))
        return collected

    def __blackhole(self, data, u=None):
        return data

    def __blackhole2(self, data, u=None):
        return []

    def _requests_events(self, API_ENDPOINT, EXTRA_HEADERS=None):
        MAIN_HEAD = {"User-Agent": "VTHellAutoScheduler/2.2"}
        if EXTRA_HEADERS:
            for k, v in EXTRA_HEADERS.items():
                MAIN_HEAD[k] = v
        req = requests.get(API_ENDPOINT, headers=MAIN_HEAD)
        if req.status_code >= 400:
            vtlog.error("Can't fetch API")
            return None, "Can't fetch API"
        try:
            scheduled_streams = req.json()
        except json.JSONDecodeError:
            vtlog.error("API returned weird stuff, aborting...")
            return None, "API returned weird stuff, aborting..."
        return scheduled_streams, "Success"

    def ignore_dataset(self, event_data, disabled):
        callback = {
            "word": self.__ignore_word,
            "channel": self.__ignore_channel,
        }
        for ignore in disabled:
            vtlog.debug(
                "Ignoring: {} -- {}".format(ignore["type"], ignore["data"])
            )
            event_data = callback.get(ignore["type"], self.__blackhole)(
                event_data, ignore["data"]
            )
        return event_data

    def collect_dataset(self, event_data, allowed):
        callback = {
            "word": self.__collect_word,
            "channel": self.__collect_channel,
        }
        collected_streams = []
        for enable in allowed:
            vtlog.debug(
                "Collecting: {} -- {}".format(enable["type"], enable["data"])
            )
            collect = callback.get(enable["type"], self.__blackhole2)(
                event_data, enable["data"]
            )
            collected_streams.extend(collect)
        return collected_streams


class NijisanjiScheduler(AutoScheduler):

    API_ENDPOINT = "https://api.ihateani.me/nijisanji/youtube/live"
    API_ENDPOINT_BILI = "https://api.ihateani.me/nijisanji/live"

    def __init__(self, allowed_data, denied_data, enable_bili=False):
        self.ENABLED = allowed_data
        self.DISABLED = denied_data
        self._bilibili = enable_bili
        self.__format_console()

    def __format_console(self):
        vtlog.removeHandler(console)
        formatter1 = logging.Formatter("[%(asctime)s] Nijisanji: %(message)s")
        console.setFormatter(formatter1)
        vtlog.addHandler(console)

    def __filter_upcoming(self, event_data):
        event_data = event_data["upcoming"]
        upcoming = []
        current_time = datetime.utcnow().timestamp()
        for event in event_data:
            if current_time >= int(event["startTime"]):
                continue
            upcoming.append(event)
        return upcoming

    def __process_bilibili(self):
        vtlog.info("Fetching BiliBili Schedule API.")
        events_data, msg = self._requests_events(self.API_ENDPOINT_BILI)
        if not events_data:
            return []

        events_data = self.__filter_upcoming(events_data)

        vtlog.info("Collecting BiliBili live data...")
        events_data = self.ignore_dataset(events_data, self.DISABLED)
        collected_streams = self.collect_dataset(events_data, self.ENABLED)
        return collected_streams

    def process(self):
        vtlog.info("Fetching YouTube Schedule API.")
        events_data, msg = self._requests_events(self.API_ENDPOINT)
        if not events_data:
            return []

        events_data = self.__filter_upcoming(events_data)

        vtlog.info("Collecting YouTube live data...")
        events_data = self.ignore_dataset(events_data, self.DISABLED)
        collected_streams = self.collect_dataset(events_data, self.ENABLED)
        if self._bilibili:
            collected_streams.extend(self.__process_bilibili())
        return collected_streams


class HololiveScheduler(AutoScheduler):

    API_ENDPOINT = "https://api.holotools.app/v1/live"
    API_ENDPOINT_BILI = "https://api.ihateani.me/live"

    def __init__(self, allowed_data, denied_data, enable_bili=False):
        self.ENABLED = allowed_data
        self.DISABLED = denied_data
        self._bilibili = enable_bili
        self.__format_console()

    def __format_console(self):
        vtlog.removeHandler(console)
        formatter1 = logging.Formatter("[%(asctime)s] Hololive: %(message)s")
        console.setFormatter(formatter1)
        vtlog.addHandler(console)

    def __filter_upcoming(self, event_data):
        event_data = event_data["upcoming"]
        upcoming = []
        current_time = datetime.utcnow().timestamp()
        for event in event_data:
            if current_time >= int(event["startTime"]):
                continue
            if event["platform"] == "youtube":
                upcoming.append(event)
        return upcoming

    def __process_bilibili(self):
        vtlog.info("Fetching BiliBili Schedule API.")
        events_data, msg = self._requests_events(self.API_ENDPOINT_BILI)
        if not events_data:
            return []

        events_data = self.__filter_upcoming(events_data)

        vtlog.info("Collecting BiliBili live data...")
        events_data = self.ignore_dataset(events_data, self.DISABLED)
        collected_streams = self.collect_dataset(events_data, self.ENABLED)
        return collected_streams

    def __process_youtube(self):
        events_data, msg = self._requests_events(self.API_ENDPOINT)
        if not events_data:
            return []

        parsed_upcoming = []
        current_time = datetime.now(tz=timezone.utc).timestamp()
        vtlog.info("Parsing results...")
        for upcome in events_data["upcoming"]:
            if not upcome["yt_video_key"]:
                continue  # Is bilibili

            proper_parsed = {
                "id": "",
                "channel": "",
                "startTime": 0,
                "status": "upcoming",
                "title": "",
                "platform": "youtube",
            }
            utc_time = upcome["live_schedule"].replace("Z", "")
            try:
                parsed_date = datetime.strptime(
                    utc_time, "%Y-%m-%dT%H:%M:%S.%f"
                ).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                parsed_date = datetime.strptime(
                    utc_time, "%Y-%m-%dT%H:%M:%S"
                ).replace(tzinfo=timezone.utc).timestamp()
            parsed_date = int(parsed_date)
            if current_time >= parsed_date:
                continue
            proper_parsed["id"] = upcome["yt_video_key"]
            proper_parsed["channel"] = upcome["channel"]["yt_channel_id"]
            proper_parsed["startTime"] = parsed_date
            proper_parsed["title"] = upcome["title"]
            parsed_upcoming.append(proper_parsed)
        return parsed_upcoming

    def process(self):
        vtlog.info("Fetching YouTube Schedule API.")
        events_data = self.__process_youtube()

        vtlog.info("Collecting YouTube live data...")
        events_data = self.ignore_dataset(events_data, self.DISABLED)
        collected_streams = self.collect_dataset(events_data, self.ENABLED)
        if self._bilibili:
            collected_streams.extend(self.__process_bilibili())
        return collected_streams


def announce_shit(msg="Unknown"):
    if not DISCORD_WEBHOOK_URL:
        vtlog.debug("No Discord Webhook url, skipping announcement...")
        return
    webhook = DiscordWebhook(
        url=DISCORD_WEBHOOK_URL, username="VTHell Auto Scheduler"
    )
    embed = DiscordEmbed(title="VTHell", color=5574409)
    embed.set_timestamp()

    embed.add_embed_field(name="Message", value=msg)

    webhook.add_embed(embed)
    webhook.execute()


with open(
    pjoin(BASE_VTHELL_PATH, "dataset", "_auto_scheduler.json"),
    "r",
    encoding="utf-8",
) as fp:
    SCHEDULER_MAP = json.load(fp)
    ENABLED_MAP = SCHEDULER_MAP["enabled"]
    IGNORED_MAP = SCHEDULER_MAP["disabled"]

niji_set = []
holo_set = []

collected_streams = []

if PROCESS_HOLOLIVE:
    holo = HololiveScheduler(ENABLED_MAP, IGNORED_MAP, ENABLE_BILIBILI)
    holo_set = holo.process()

if PROCESS_NIJISANJI:
    niji = NijisanjiScheduler(ENABLED_MAP, IGNORED_MAP, ENABLE_BILIBILI)
    niji_set = niji.process()

collected_streams.extend(holo_set)
collected_streams.extend(niji_set)

vtlog.removeHandler(console)
formatter1 = logging.Formatter("[%(asctime)s] %(message)s")
console.setFormatter(formatter1)
vtlog.addHandler(console)

vtlog.debug("Total Holo Stream: {}".format(len(holo_set)))
vtlog.debug("Total Niji Stream: {}".format(len(niji_set)))

if not collected_streams:
    vtlog.info("No streams that match on current rule, exiting...")
    exit(0)

vtlog.info(
    "Live data collected and filtered, now trying to add to jobs list..."
)

for stream in collected_streams:
    if stream.id in vthell_jobs:
        vtlog.warn("Skipping {}, jobs already made!".format(stream.id))
        continue
    job_file = pjoin(BASE_VTHELL_PATH, "jobs", stream.id + ".json")
    with open(job_file, "w") as fp:
        json.dump(
            stream.to_dict(), fp, indent=2,
        )
    vtlog.info("Added {} to jobs list".format(stream.id))
    announce_shit("Added: {}".format(stream.stream_url))
