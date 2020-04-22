import glob
import json
import logging
import os
import sys
from datetime import datetime

import pytz
import requests
from discord_webhook import DiscordEmbed, DiscordWebhook

"""
Using jetri web API because it's easier :D
"""

BASE_VTHELL_PATH = "/media/sdac/mizore/vthell/"  # Absoule path to vthell folder

DISCORD_WEBHOOK_URL = os.getenv("VTHELL_DISCORD_WEBHOOK", "")


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


ENABLED_MAP = [
    {"type": "channel", "data": "UC1uv2Oq6kNxgATlCiez59hw"},
    {"type": "channel", "data": "UChAnqc_AY5_I3Px5dig3X1Q"},
    {"type": "word", "data": "歌う"},
    {"type": "word", "data": "歌枠"},
    {"type": "word", "data": "歌雑談"},
    {"type": "word", "data": "ASMR"},
    {"type": "word", "data": "うたうよ"}
]

IGNORED_MAP = [
    {"type": "word", "data": "(cover)"},
    {"type": "word", "data": "あさココ"},
    {"type": "dataset", "data": "nijisanji"},
    {"type": "dataset", "data": "holostars"},
    {"type": "dataset", "data": "hololivecn"},
]

vtlog.info("Fetching live data from API...")
r = requests.get("https://storage.googleapis.com/vthell-data/live.json")
if r.status_code >= 400:
    vtlog.error("Cant fetch API")
    exit(1)
try:
    scheduled_streams = r.json()
except json.JSONDecodeError:
    vtlog.error("API returned weird stuff, aborting...")
    exit(1)


def _collect_title(data):
    title_set = []
    for k, vv in data.items():
        for ni, i in enumerate(vv):
            t_ = {"t": i["title"], "i": ni, "k": k}
            title_set.append(t_)
    return title_set


def _ignore_channel(data, channel):
    if channel in data:
        del data[channel]
    return data


def _ignore_word(data, word):
    title_set = _collect_title(data)
    for title in title_set:
        if word in title["t"]:
            del data[title["k"]][title["i"]]
    return data


def _collect_word(data, word):
    title_set = _collect_title(data)
    collected = []
    for t in title_set:
        if word in t["t"]:
            dt = data[t["k"]][t["i"]]
            dt["streamer"] = t["k"]
            collected.append(dt)
    return collected


def _collect_channel(data, channel):
    collected = []
    if channel in data:
        for st in data[channel]:
            st["streamer"] = channel
            collected.append(st)
    return collected


def _blackhole(data, u=None):
    return data


def _blackhole2(data, u=None):
    return []


vtlog.info("Collecting live data...")
for ignore in IGNORED_MAP:
    vtlog.debug("Ignoring: {}\n{}".format(ignore["type"], ignore["data"]))
    m_ = {"word": _ignore_word, "channel": _ignore_channel}
    scheduled_streams = m_.get(ignore["type"], _blackhole)(
        scheduled_streams, ignore["data"]
    )

collected_streams = []
for enable in ENABLED_MAP:
    vtlog.debug("Collecting: {}\n{}".format(enable["type"], enable["data"]))
    m_ = {"word": _collect_word, "channel": _collect_channel}
    collect = m_.get(enable["type"], _blackhole2)(
        scheduled_streams, enable["data"]
    )
    collected_streams.extend(collect)


def format_filename(title, ctime, s_id):
    if isinstance(ctime, str):
        ctime = int(ctime)
    tsd = datetime.fromtimestamp(ctime, pytz.timezone("Asia/Tokyo"))
    ts_strf = tsd.strftime("[%Y.%m.%d]")
    ts_strf = ts_strf[:-1] + ".{}]".format(s_id)
    return secure_filename("{} {} [1080p AAC]".format(ts_strf, title))


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
    final_filename = format_filename(stream["title"], stream["startTime"], stream["id"])
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
    announce_shit("Added: https://www.youtube.com/watch?v={}".format(stream["id"]))
