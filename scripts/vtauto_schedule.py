import glob
import json
import logging
import os
import re
import sys
from datetime import datetime

import pytz
import requests
from discord_webhook import DiscordEmbed, DiscordWebhook

"""
A tools to automatically schedule upcoming streams!
Only support Hololive and Nijisanji Main Group (Everyone except World)

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
        logging.FileHandler(BASE_VTHELL_PATH + "nvthell.log", "a", "utf-8")
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
vthell_jobs = glob.glob(BASE_VTHELL_PATH + "jobs/*.json")
vthell_jobs = [
    os.path.splitext(os.path.basename(job))[0] for job in vthell_jobs
]


class AutoScheduler:
    """Main filtering and request process in here."""

    def __init__(self):
        self._ignore = True

    def __collect_title(self, data):
        title_set = []
        for k, vv in data.items():
            for ni, i in enumerate(vv):
                t_ = {"t": i["title"], "i": ni, "k": k}
                title_set.append(t_)
        return title_set

    def __ignore_channel(self, data, channel):
        if channel in data:
            del data[channel]
        return data

    def __ignore_word(self, data, word):
        title_set = self.__collect_title(data)
        for title in title_set:
            if word in title["t"]:
                del data[title["k"]][title["i"]]
        return data

    def __collect_word(self, data, word):
        title_set = self.__collect_title(data)
        collected = []
        for t in title_set:
            if word in t["t"]:
                dt = data[t["k"]][t["i"]]
                dt["streamer"] = t["k"]
                collected.append(dt)
        return collected

    def __collect_channel(self, data, channel):
        collected = []
        if channel in data:
            for st in data[channel]:
                st["streamer"] = channel
                collected.append(st)
        return collected

    def __blackhole(self, data, u=None):
        return data

    def __blackhole2(self, data, u=None):
        return []

    def _requests_events(self, API_ENDPOINT):
        req = requests.get(
            API_ENDPOINT, headers={"User-Agent": "VTHellAutoScheduler/1.9"}
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
        for ignore in disabled:
            vtlog.debug(
                "Ignoring: {} -- {}".format(ignore["type"], ignore["data"])
            )
            m_ = {"word": self.__ignore_word, "channel": self.__ignore_channel}
            event_data = m_.get(ignore["type"], self.__blackhole)(
                event_data, ignore["data"]
            )
        return event_data

    def collect_dataset(self, event_data, allowed):
        collected_streams = []
        for enable in allowed:
            vtlog.debug(
                "Collecting: {} -- {}".format(enable["type"], enable["data"])
            )
            m_ = {
                "word": self.__collect_word,
                "channel": self.__collect_channel,
            }
            collect = m_.get(enable["type"], self.__blackhole2)(
                event_data, enable["data"]
            )
            collected_streams.extend(collect)
        return collected_streams


class NijisanjiScheduler(AutoScheduler):

    API_ENDPOINT = "https://api.itsukaralink.jp/v1.2/events.json"

    def __init__(self, allowed_data, denied_data):
        self.ENABLED = allowed_data
        self.DISABLED = denied_data
        self.__format_console()
        self.__load_dataset()

    def __load_dataset(self):
        with open(
            BASE_VTHELL_PATH + "nijisanji.json", "r", encoding="utf-8"
        ) as fp:
            vtlog.debug("Loading dataset...")
            self.dataset = json.load(fp)

    def __format_console(self):
        vtlog.removeHandler(console)
        formatter1 = logging.Formatter("[%(asctime)s] Nijisanji: %(message)s")
        console.setFormatter(formatter1)
        vtlog.addHandler(console)

    def __jst_to_utctimestamp(self, timedata: str) -> float:
        parse_dt = datetime.strptime(timedata, "%Y-%m-%dT%H:%M:%S.%f+09:00")
        parse_dt = parse_dt.timestamp() - (9 * 60 * 60)
        return parse_dt

    def __filter_events(self, events: list) -> list:
        filtered = []
        for event in events:
            parse_dt = self.__jst_to_utctimestamp(event["start_date"])
            ts = datetime.now(pytz.timezone("UTC")).timestamp()
            if parse_dt - 120 > ts:
                filtered.append(event)
        vtlog.debug(
            "Filtered result: {} (from: {})".format(len(filtered), len(events))
        )
        return filtered

    def __find_vliver(self, vliver_id):
        for vliver in self.dataset["vliver"]:
            if vliver_id == vliver["id"]:
                return vliver

    def __internal_processor(self, events: list) -> list:
        processed_data = {}
        for event in events:
            vliver = self.__find_vliver(event["livers"][0]["id"])
            vliver_chan = vliver["youtube"]
            dataset = []
            if vliver_chan in processed_data:
                dataset = processed_data[vliver_chan]
            d = {}
            v_id = event["url"]
            v_id = re.search(
                r"https\:\/\/www\.youtube\.com/watch\?v=(?P<ids>.*)", v_id
            )
            d["id"] = v_id.group("ids")
            d["title"] = event["name"]
            d["type"] = "upcoming"
            start_time = self.__jst_to_utctimestamp(event["start_date"])
            start_time = int(round(start_time))
            d["startTime"] = str(start_time)
            dataset.append(d)
            processed_data[vliver_chan] = dataset
        return processed_data

    def process(self):
        vtlog.info("Fetching Nijisanji Schedule API.")
        events_data, msg = self._requests_events(self.API_ENDPOINT)
        if not events_data:
            return []

        events_data = events_data["data"]["events"]

        vtlog.info("Filtering data...")
        events_data = self.__filter_events(events_data)
        processed_data = self.__internal_processor(events_data)

        vtlog.info("Collecting live data...")
        processed_data = self.ignore_dataset(processed_data, self.DISABLED)
        collected_streams = self.collect_dataset(processed_data, self.ENABLED)
        return collected_streams


class HololiveScheduler(AutoScheduler):

    API_ENDPOINT = "https://storage.googleapis.com/vthell-data/live.json"

    def __init__(self, allowed_data, denied_data):
        self.ENABLED = allowed_data
        self.DISABLED = denied_data
        self.__format_console()

    def __format_console(self):
        vtlog.removeHandler(console)
        formatter1 = logging.Formatter("[%(asctime)s] Hololive: %(message)s")
        console.setFormatter(formatter1)
        vtlog.addHandler(console)

    def process(self):
        vtlog.info("Fetching Hololive Schedule API.")
        events_data, msg = self._requests_events(self.API_ENDPOINT)
        if not events_data:
            return []

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


def secure_filename(fn: str):
    fn = fn.replace("/", "／")
    fn = fn.replace(":", "：")
    fn = fn.replace("<", "＜")
    fn = fn.replace(">", "＞")
    fn = fn.replace('"', "”")
    fn = fn.replace("\\", "＼")
    fn = fn.replace("?", "？")
    fn = fn.replace("*", "⋆")
    fn = fn.replace("|", "｜")
    fn = fn.replace("#", "")
    return fn


def format_filename(title, ctime, s_id):
    if isinstance(ctime, str):
        ctime = int(ctime)
    tsd = datetime.fromtimestamp(ctime, pytz.timezone("Asia/Tokyo"))
    ts_strf = tsd.strftime("[%Y.%m.%d]")
    ts_strf = ts_strf[:-1] + ".{}]".format(s_id)
    return secure_filename("{} {} [1080p AAC]".format(ts_strf, title))


ENABLED_MAP = [
    {"type": "channel", "data": "UC1uv2Oq6kNxgATlCiez59hw"},
    {"type": "channel", "data": "UChAnqc_AY5_I3Px5dig3X1Q"},
    {"type": "word", "data": "歌う"},
    {"type": "word", "data": "歌枠"},
    {"type": "word", "data": "歌雑談"},
    {"type": "word", "data": "ASMR"},
    {"type": "word", "data": "うたうよ"},
]

IGNORED_MAP = [
    {"type": "channel", "data": "UCjlmCrq4TP1I4xguOtJ-31w"},
    {"type": "channel", "data": "UCGNI4MENvnsymYjKiZwv9eg"},
    {"type": "channel", "data": "UC9mf_ZVpouoILRY9NUIaK-w"},
    {"type": "channel", "data": "UCEzsociuFqVwgZuMaZqaCsg"},
    {"type": "channel", "data": "UCANDOlYTJT7N5jlRC3zfzVA"},
    {"type": "channel", "data": "UCNVEsYbiZjH5QLmGeSgTSzg"},
    {"type": "channel", "data": "UC6t3-_N8A6ME1JShZHHqOMw"},
    {"type": "channel", "data": "UCKeAhJvy8zgXWbh9duVjIaQ"},
    {"type": "channel", "data": "UCJFZiqLMntJufDCHc6bQixg"},
    {"type": "channel", "data": "UCZgOv3YDEs-ZnZWDYVwJdmA"},
    {"type": "word", "data": "(cover)"},
    {"type": "word", "data": "あさココ"},
]

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
    if stream["id"] in vthell_jobs:
        vtlog.warn("Skipping {}, jobs already made!".format(stream["id"]))
        continue
    if stream["type"] != "upcoming":
        vtlog.warn(
            "Skipping {} because it's not an upcoming stream".format(
                stream["id"]
            )
        )
        continue
    final_filename = format_filename(
        stream["title"], stream["startTime"], stream["id"]
    )
    dts_ts = datetime.fromtimestamp(int(stream["startTime"])).timestamp()
    with open(BASE_VTHELL_PATH + "jobs/" + stream["id"] + ".json", "w") as fp:
        json.dump(
            {
                "id": stream["id"],
                "filename": final_filename,
                "isDownloading": False,
                "isDownloaded": False,
                "isPaused": False,
                "firstRun": True,
                "startTime": dts_ts - 120,  # T-2
                "streamer": stream["streamer"],
                "streamUrl": "https://www.youtube.com/watch?v=" + stream["id"],
            },
            fp,
            indent=2,
        )
    vtlog.info("Added {} to jobs list".format(stream["id"]))
    announce_shit(
        "Added: https://www.youtube.com/watch?v={}".format(stream["id"])
    )
