import glob
import json
import logging
import os
import subprocess as sp
import sys
from datetime import datetime

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

"""
Cookies must be Netscape format or the one that can be opened with CURL.

Netscape format:
URL  INCLUDE_SUBDOMAINS  PATH  HTTPS_ONLY  EXPIRES  COOKIES_NAME  COOKIES_VALUE
.youtube.com  TRUE  /  TRUE  0  SAMPLES  SAMPLEVALUES
"""
COOKIES_NAME = "cookies.txt"  # Your cookies file name

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(BASE_VTHELL_PATH + "nvthell.log", "a", "utf-8")
    ],
    format="%(asctime)s %(name)-1s -- [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
vtlog = logging.getLogger("vthell")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)


def announce_shit(msg="Unknown"):
    if not DISCORD_WEBHOOK_URL:
        vtlog.debug("No Discord Webhook url, skipping announcement...")
        return
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, username="VTHell")
    embed = DiscordEmbed(title="VTHell", color=5574409)
    embed.set_timestamp()

    embed.add_embed_field(name="Message", value=msg)

    webhook.add_embed(embed)
    webhook.execute()


def find_and_parse_cookies() -> list:
    """Find provided cookies and parse them"""
    if not os.path.isfile(BASE_VTHELL_PATH + COOKIES_NAME):
        return []
    vtlog.info("Opening cookies file...")
    cookies_data = open(
        BASE_VTHELL_PATH + COOKIES_NAME, "r", encoding="utf-8"
    ).readlines()
    vtlog.info("Parsing cookies file...")
    cookies_data = [c.rstrip() for c in cookies_data if not c.startswith("#")]

    parsed_cookies = []
    for kuki in cookies_data:
        try:
            (
                uri,
                inc_subdomain,
                path,
                https_only,
                expires,
                name,
                value,
            ) = kuki.split("\t")
        except ValueError:
            vtlog.error(
                "Failed to unpack cookies, "
                "please provide a valid netscape format"
            )
            return []
        if ("youtube.com" or "youtu.be" or "bilibili.com") not in uri:
            continue
        parsed_cookies.append("--http-cookie")
        parsed_cookies.append('"{k}={v}"'.format(k=name, v=value))
    vtlog.debug("Total cookies keys: {}".format(len(parsed_cookies) // 2))
    vtlog.info("Cookies parsed!")
    return parsed_cookies


def reset_handler(r=True):
    if r:
        vtlog.removeHandler(console)
    formatter0 = logging.Formatter("%(message)s")
    console.setFormatter(formatter0)
    vtlog.addHandler(console)


def print_end():
    vtlog.info("====================== End of process! ======================")


reset_handler(False)

with open(BASE_VTHELL_PATH + "/dataset/_youtube_mapping.json") as fp:
    upload_mapping = json.load(fp)

with open(BASE_VTHELL_PATH + "/dataset/_bilibili_mapping.json") as fp:
    bilibili_temp = json.load(fp)
    for k, v in bilibili_temp.items():
        upload_mapping[k] = v

vtlog.info("====================== Start of process! ======================")

UPLOAD_CMD = [RCLONE_PATH, "-v", "-P", "copy"]
MKVMERGE_CMD = ["mkvmerge", "-o"]
MKVMERGE_LANG = ["--language", "0:jpn", "--language", "1:jpn"]
UPLOAD_BASE_PATH = RCLONE_TARGET_BASE + "Stream Archive/{}"

vtlog.removeHandler(console)
formatter1 = logging.Formatter("[%(asctime)s] %(message)s")
console.setFormatter(formatter1)
vtlog.addHandler(console)

vtlog.info("Collecting jobs...")
vthell_jobs = glob.glob(BASE_VTHELL_PATH + "jobs/*.json")

if not vthell_jobs:
    vtlog.info("No jobs, exiting...")
    reset_handler()
    print_end()
    exit(0)

vthell_stream = None
for vthjs in vthell_jobs:
    STREAMLINK_CMD = [BASE_VENV_BIN + "streamlink", "-o"]
    dtnow = datetime.now().timestamp()
    with open(vthjs, "r") as fp:
        vt = json.load(fp)
    if vt["isDownloaded"]:
        vtlog.warn("Skipping {}, reason: Already recorded.".format(vt["id"]))
        continue
    if vt["isDownloading"]:
        vtlog.warn(
            "Skipping {}, reason: Currently recording.".format(vt["id"])
        )
        continue
    if vt["isPaused"]:
        vtlog.warn("Skipping {}, reason: Currently paused.".format(vt["id"]))
        continue
    if vt["startTime"] > dtnow:
        vtlog.warn(
            "Skipping {}, reason: Still far away from scheduled time.".format(
                vt["id"]
            )
        )
        continue
    if dtnow > (vt["startTime"] + 300) and not vt["firstRun"]:
        vtlog.warn(
            "Skipping {}, reason: Stream haven't started "
            "since 3 minutes, pausing...".format(vt["id"])
        )
        announce_shit(
            "Stream ID: " + vt["id"] + " are paused, please check it."
        )
        vt["isPaused"] = True
        vt["overridePaused"] = False
        with open(vthjs, "w") as fp:
            json.dump(vt, fp, indent=2)
        continue
    if vt["firstRun"]:
        vt["firstRun"] = False
    vtlog.info("Unrecorded stream found, starting...")
    save_ts_name = (
        "'" + BASE_VTHELL_PATH + "streamdump/" + vt["filename"] + ".ts'"
    )

    vtlog.info("Starting job for: {}".format(vt["id"]))
    vtlog.debug("Output: {}".format(save_ts_name))
    STREAMLINK_CMD.append(save_ts_name)
    STREAMLINK_CMD.extend(find_and_parse_cookies())
    STREAMLINK_CMD.extend([vt["streamUrl"], "best"])
    vt["isDownloading"] = True

    with open(vthjs, "w") as fp:
        json.dump(vt, fp, indent=2)

    vtlog.removeHandler(console)
    formatter2 = logging.Formatter(
        "[%(asctime)s] Job {}:  %(message)s".format(vt["id"])
    )
    console.setFormatter(formatter2)
    vtlog.addHandler(console)

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
        if line.startswith("error") or line.startswith("streamlink: error"):
            if "read timeout" in line:
                override_err = True
            if "429 client error" in line:
                req_limit_err = True
            if "unrecognized" in line:
                args_unk_err = True
        if "opening stream" in line and not discord_announced:
            discord_announced = True
            announce_shit("Job " + vt["id"] + " started recording!")

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
                "Job: " + vt["id"] + " >> 429 Error, please enable proxy."
            )
        if args_unk_err:
            announce_shit("Job: " + vt["id"] + " >> Please check output name.")
        vt["isDownloading"] = False
        with open(vthjs, "w") as fp:
            json.dump(vt, fp, indent=2)
        continue
    else:
        vthell_stream = vt
        break

if not vthell_stream:
    vtlog.info("No scheduled streams that met conditions, exiting...")
    reset_handler()
    print_end()
    exit(0)

vtjsf = BASE_VTHELL_PATH + "jobs/" + vthell_stream["id"] + ".json"

save_mux_name = (
    BASE_VTHELL_PATH + "streamdump/" + vthell_stream["filename"] + ".mkv"
)
save_ts_name1 = (
    BASE_VTHELL_PATH + "streamdump/" + vthell_stream["filename"] + ".ts"
)

announce_shit(
    "Stream ID: "
    + vthell_stream["id"]
    + " are finished recording, will be muxed and uploaded."
)
vtlog.info(
    "Job {} recording finished, now muxing...".format(vthell_stream["id"])
)
vthell_stream["isDownloading"] = False
vthell_stream["isDownloaded"] = True
with open(vtjsf, "w") as fp:
    json.dump(vthell_stream, fp)


MKVMERGE_CMD.append(save_mux_name)
MKVMERGE_CMD.extend(MKVMERGE_LANG)
MKVMERGE_CMD.append(save_ts_name1)

vtlog.info("Executing mkvmerge command!")
vtlog.debug(" ".join(MKVMERGE_CMD))
sp.call(MKVMERGE_CMD)

if os.path.isfile(save_mux_name) and os.path.getsize(save_mux_name) > 0:
    UPLOAD_CMD.extend(
        [
            save_mux_name,
            UPLOAD_BASE_PATH.format(
                upload_mapping.get(vthell_stream["streamer"], {}).get(
                    "upload_path", "Unknown"
                )
            ),
        ]
    )
    vtlog.info("Executing rclone command!")
    vtlog.debug(" ".join(UPLOAD_CMD))
    sp.call(UPLOAD_CMD)
    os.remove(save_mux_name)

vtlog.info("Cleaning up...")
os.remove(vtjsf)
os.remove(save_ts_name1)

reset_handler()
print_end()
