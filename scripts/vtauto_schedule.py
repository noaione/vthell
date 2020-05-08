import glob
import json
import logging
import os
import sys
from datetime import datetime
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
"""
PROCESS_HOLOLIVE = True
PROCESS_NIJISANJI = False

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

    def __init__(self, data: dict):
        self._st_data = data
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self._filename,
            "startTime": self._start_time - 60,
            "streamer": self._streamer,
            "streamUrl": self.BASE_YT_WATCH + self.id,
            "type": "youtube",
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

    def __ignore_channel(self, data, channel):
        new_data = []
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
                collected.append(StreamData(st))
        return collected

    def __collect_channel(self, data, channel):
        collected = []
        for st in data:
            if channel == st["channel"]:
                collected.append(StreamData(st))
        return collected

    def __blackhole(self, data, u=None):
        return data

    def __blackhole2(self, data, u=None):
        return []

    def _requests_events(self, API_ENDPOINT):
        req = requests.get(
            API_ENDPOINT, headers={"User-Agent": "VTHellAutoScheduler/2.1"}
        )
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

    API_ENDPOINT = "https://api.jetri.co/nijisanji/live"

    def __init__(self, allowed_data, denied_data):
        self.ENABLED = allowed_data
        self.DISABLED = denied_data
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

    def process(self):
        vtlog.info("Fetching Nijisanji Schedule API.")
        events_data, msg = self._requests_events(self.API_ENDPOINT)
        if not events_data:
            return []

        events_data = self.__filter_upcoming(events_data)

        vtlog.info("Collecting live data...")
        events_data = self.ignore_dataset(events_data, self.DISABLED)
        collected_streams = self.collect_dataset(events_data, self.ENABLED)
        return collected_streams


class HololiveScheduler(AutoScheduler):

    API_ENDPOINT = "https://api.jetri.co/live"

    def __init__(self, allowed_data, denied_data):
        self.ENABLED = allowed_data
        self.DISABLED = denied_data
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
            upcoming.append(event)
        return upcoming

    def process(self):
        vtlog.info("Fetching Hololive Schedule API.")
        events_data, msg = self._requests_events(self.API_ENDPOINT)
        if not events_data:
            return []

        events_data = self.__filter_upcoming(events_data)

        vtlog.info("Collecting live data...")
        events_data = self.ignore_dataset(events_data, self.DISABLED)
        collected_streams = self.collect_dataset(events_data, self.ENABLED)
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
    holo = HololiveScheduler(ENABLED_MAP, IGNORED_MAP)
    holo_set = holo.process()

if PROCESS_NIJISANJI:
    niji = NijisanjiScheduler(ENABLED_MAP, IGNORED_MAP)
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
    announce_shit(
        "Added: https://www.youtube.com/watch?v={}".format(stream.id)
    )
