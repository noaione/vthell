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


MAPPING = {
    # Other
    "Hololive Official": "UCJFZiqLMntJufDCHc6bQixg",
    # Gen 0
    "AZKi": "UC0TXe_LYZ4scaW2XMyi5_kw",
    "Hoshimachi Suisei": "UC5CwaMl1eIgY8h02uZw7u8A",
    "Roboco-san": "UCDqI2jOz0weumE8s7paEk6g",
    "Sakura Miko": "UC-hM6YJuNYVAmUWxeIr9FeA",
    "Tokina Sora": "UCp6993wxpyDPHUpavwDFqgg",
    # GAMERS
    "Inugami Korone": "UChAnqc_AY5_I3Px5dig3X1Q",
    "Nekomata Okayu": "UCvaTdHTWBGv3MKj3KVqJVCw",
    "Shirakami Fubuki": "UCdn5BQ06XqgXoAxIhbqw5Rg",
    "Okami Mio": "UCp-5t9SrOQwXMU7iIjQfARg",
    # Gen 1
    "Akai Haato": "UC1CfXB_kRs3C-zaeTG3oGyg",
    "Akai Haato Sub ch": "UCHj_mh57PVMXhAUDphUQDFA",
    "Aki Rosenthal": "UCFTLzh12_nrtzqBPsTCqenA",
    "Natsuiro Matsuri": "UCQ0UDLQCjY0rmuxCDE38FGg",
    "Yozora Mel": "UCD8HOxPs4Xvsm8H0ZxXGiBw",
    # Gen 2
    "Minato Aqua": "UC1opHUrw8rvnsadT-iGp7Cg",
    "Murasaki Shion": "UCXTpFs_3PqI41qX2d9tL2Rw",
    "Nakiri Ayame": "UC7fk0CB07ly8oSl0aqKkqFg",
    "Oozora Subaru": "UCvzGlP9oQwU--Y0r9id_jnA",
    "Yuzuki Choco": "UC1suqwovbL1kzsoaZgFZLKg",
    "Yuzuki Choco Sub ch": "UCp3tgHXw_HI0QMk1K8qh3gQ",
    # Gen 3
    "Houshou Marine": "UCCzUftO8KOVkV4wQG1vkUvg",
    "Shiranui Flare": "UCvInZx9h3jC2JzsIzoOebWg",
    "Shirogane Noel": "UCdyqAaZDKHXg4Ahi7VENThQ",
    "Uruha Rushia": "UCl_gCybOJRIgOXw6Qb4qJzQ",
    "Usada Pekora": "UC1DCedRgGHBdm81E1llLhOQ",
    # Gen 4
    "Amane Kanata": "UCZlDXzGoo7d44bwdNObFacg",
    "Himemori Luna": "UCa9Y57gfeY0Zro_noHRVrnw",
    "Kiryu Coco": "UCS9uQI-jC3DE0L4IpXyvr6w",
    "Tokoyami Towa": "UC1uv2Oq6kNxgATlCiez59hw",
    "Tsunomaki Watame": "UCqm3BQLlJfvkTsX_hvm0UmA",
    # HoloID - Gen 1
    "Ayunda Risu": "UCOyYb1c43VlX9rc_lT6NKQw",
    "Moona Hoshinova": "UCP0BspO_AMEe3aQqqpo89Dg",
    "Airani Iofifteen": "UCAoy6rzhSf4ydcYjJw3WoVg",
}

ENABLED_MAP = [
    {"type": "channel", "data": "UC1uv2Oq6kNxgATlCiez59hw"},
    {"type": "channel", "data": "UChAnqc_AY5_I3Px5dig3X1Q"},
    {"type": "channel", "data": "UC5CwaMl1eIgY8h02uZw7u8A"},
    {"type": "word", "data": "歌う"},
    {"type": "word", "data": "歌枠"},
]

IGNORED_MAP = [
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

vtlog.info("Fetching live data from API...")
r = requests.get("https://storage.googleapis.com/vthell-data/live.json")
if r.status_code >= 400:
    vtlog.error("Cant fetch API")
    exit(1)
try:
    scheduled_streams = r.json()
except json.JSONDecodeError:
    vtlog.error("API returned weird shit")
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

collected = []
for enable in ENABLED_MAP:
    vtlog.debug("Collecting: {}\n{}".format(enable["type"], enable["data"]))
    m_ = {"word": _collect_word, "channel": _collect_channel}
    collect = m_.get(enable["type"], _blackhole2)(
        scheduled_streams, enable["data"]
    )
    collected.extend(collect)


def format_filename(title, ctime):
    if isinstance(ctime, str):
        ctime = int(ctime)
    tsd = datetime.fromtimestamp(ctime, pytz.timezone("Asia/Tokyo"))
    ts_strf = tsd.strftime("[%Y.%m.%d]")
    return "{} {} [1080p AAC]".format(ts_strf, title)


vtlog.info(
    "Live data collected and filtered, now trying to add to jobs list..."
)

for stream in collected:
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
    final_filename = format_filename(stream["title"], stream["startTime"])
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
