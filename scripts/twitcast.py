import glob
import json
import logging
import os
import subprocess as sp
import sys
from datetime import datetime
from os.path import join as pjoin

import pytz
import requests
from discord_webhook import DiscordEmbed, DiscordWebhook

BASE_VTHELL_PATH = (
    "/media/sdac/mizore/vthell/"  # Absoule path to vthell folder
)
RCLONE_PATH = "/media/sdac/mizore/bin/rclone"  # path to rclone executable
RCLONE_TARGET_BASE = (
    "naomeme:Backup/VTuberHell/"  # base target upload drive and folder
)
BASE_VENV_BIN = (
    "/media/sdac/mizore/pip3/bin/"  # path to created python3 virtualenv bin
)
DISCORD_WEBHOOK_URL = os.getenv("VTHELL_DISCORD_WEBHOOK", "")

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(pjoin(BASE_VTHELL_PATH, "nvthell.log"), "a", "utf-8")
    ],
    format="%(asctime)s %(name)-1s -- [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
vtlog = logging.getLogger("vthell_twitcasting")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)

# Fetch twitcast jobs (locked user, so it doesn't override.)
vtlog.info("Collecting existing jobs...")
twitcast_jobs = glob.glob(BASE_VTHELL_PATH + "jobs/*.twitcast")
twitcast_jobs = [
    os.path.splitext(os.path.basename(job))[0] for job in twitcast_jobs
]


def announce_shit(msg="Unknown"):
    if not DISCORD_WEBHOOK_URL:
        vtlog.debug("No Discord Webhook url, skipping announcement...")
        return
    webhook = DiscordWebhook(
        url=DISCORD_WEBHOOK_URL, username="VTHell Twitcasting"
    )
    embed = DiscordEmbed(title="VTHell", color=5574409)
    embed.set_timestamp()

    embed.add_embed_field(name="Message", value=msg)

    webhook.add_embed(embed)
    webhook.execute()


def reset_handler(r=True):
    if r:
        vtlog.removeHandler(console)
    formatter0 = logging.Formatter("%(message)s")
    console.setFormatter(formatter0)
    vtlog.addHandler(console)


class TwitcastingData:
    pass


reset_handler(False)

dataset_path = pjoin(BASE_VTHELL_PATH, "dataset")

with open(pjoin(dataset_path, "_twitcasting_mapping.json")) as fp:
    upload_mapping = json.load(fp)


ENABLED_USERS = ["natsuiromatsuri"]  # Enter twitcasting ID here.

BASE_URL = "https://twitcasting.tv/"
BASE_API = "https://frontendapi.twitcasting.tv/watch/user/"

STREAMLINK_CMD = [BASE_VENV_BIN + "streamlink", "-o"]
UPLOAD_CMD = [RCLONE_PATH, "-v", "-P", "copy"]
MKVMERGE_CMD = ["mkvmerge", "-o"]
MKVMERGE_LANG = ["--language", "0:jpn", "--language", "1:jpn"]
UPLOAD_BASE_PATH = RCLONE_TARGET_BASE + "Twitcasting Archive/{}"

vtlog.info("Fetching user live data from API...")
for user in ENABLED_USERS:
    if user in twitcast_jobs:
        vtlog.warn("User: {} stream are recording, skipping...".format(user))
        reset_handler()
        continue
    r = requests.post(BASE_API + user, data={"userId": user})
    if r.status_code >= 400:
        vtlog.error("Cant fetch API, continuing...")
        reset_handler()
        continue
    try:
        twitcast = r.json()
    except json.JSONDecodeError:
        vtlog.error("API returned weird shit, continuing...")
        reset_handler()
        continue
    if not twitcast["is_live"]:
        vtlog.info("User: {} are not live yet, continung...".format(user))
        reset_handler()
        continue

    TWITCAST_LOCK = BASE_VTHELL_PATH + "jobs/{}.twitcast".format(user)

    with open(TWITCAST_LOCK, "w") as fp:
        fp.write("RECORD_LOCK")

    vtlog.removeHandler(console)
    formatter2 = logging.Formatter(
        "[%(asctime)s] Job {}:  %(message)s".format(user)
    )
    console.setFormatter(formatter2)
    vtlog.addHandler(console)

    dnow = datetime.now(pytz.timezone("Asia/Tokyo"))
    dd_fn = dnow.strftime("[%Y.%m.%d-%H.%M]")
    filename = "{} {}".format(dd_fn, user)
    stream_url = BASE_URL + user

    vtlog.info("Executing streamlink command!")

    save_ts_name = "'" + BASE_VTHELL_PATH + "streamdump/" + filename + ".ts'"
    save_mux_name = BASE_VTHELL_PATH + "streamdump/" + filename + ".mkv"
    save_ts_name1 = BASE_VTHELL_PATH + "streamdump/" + filename + ".ts"

    STREAMLINK_CMD.extend([save_ts_name, stream_url, "best"])
    MKVMERGE_CMD.append(save_mux_name)
    MKVMERGE_CMD.extend(MKVMERGE_LANG)
    MKVMERGE_CMD.append(save_ts_name1)

    vtlog.info("Executing streamlink command!")
    vtlog.debug(" ".join(STREAMLINK_CMD))
    override_err = False
    req_limit_err = False
    args_unk_err = False
    discord_announced = False

    process = sp.Popen(
        " ".join(STREAMLINK_CMD),
        stdout=sp.PIPE,
        shell=True,
        stderr=sp.STDOUT,
        bufsize=1,
    )
    for line in iter(process.stdout.readline, b""):
        line = line.decode("utf-8")
        vtlog.info(line)
        line = line.lower()
        if line.startswith("error"):
            if "read timeout" in line:
                override_err = True
            if "string argument without an encoding" in line:
                override_err = True
            if "429 client error" in line:
                req_limit_err = True
            if "unrecognized arguments" in line:
                args_unk_err = True
        if "opening stream" in line and not discord_announced:
            discord_announced = True
            announce_shit("Job: " + user + " started recording!")

    process.stdout.close()
    process.wait()
    rc = process.returncode

    vtlog.info("Return code: {}".format(rc))
    vtlog.debug("Error overriden? {}".format(override_err))

    if not override_err and rc != 0:
        # Assume error
        vtlog.error("Job failed, retrying another...")
        if req_limit_err:
            announce_shit(
                "Job: " + user + " >> 429 Error, please enable proxy."
            )
        if args_unk_err:
            announce_shit("Job: " + user + " >> Please check output name.")
        os.remove(TWITCAST_LOCK)
        reset_handler()
        continue
    else:
        announce_shit(
            "Twitcast ID: " + user + " recorded, will be muxed and uploaded."
        )
        vtlog.info("Executing mkvmerge command!")
        vtlog.debug(" ".join(MKVMERGE_CMD))
        sp.call(MKVMERGE_CMD)

        if (
            os.path.isfile(save_mux_name)
            and os.path.getsize(save_mux_name) > 0
        ):
            UPLOAD_CMD.extend(
                [
                    save_mux_name,
                    UPLOAD_BASE_PATH.format(
                        upload_mapping.get(user, "Unknown")
                    ),
                ]
            )
            vtlog.info("Executing rclone command!")
            vtlog.debug(" ".join(UPLOAD_CMD))
            sp.call(UPLOAD_CMD)
            os.remove(save_mux_name)

        vtlog.info("Cleaning up...")
        os.remove(TWITCAST_LOCK)
        os.remove(save_ts_name1)

    reset_handler()
