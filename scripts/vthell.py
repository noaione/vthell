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


def reset_handler(r=True):
    if r:
        vtlog.removeHandler(console)
    formatter0 = logging.Formatter("%(message)s")
    console.setFormatter(formatter0)
    vtlog.addHandler(console)


def print_end():
    vtlog.info("====================== End of process! ======================")


reset_handler(False)

upload_mapping = {
    # Other
    "UCJFZiqLMntJufDCHc6bQixg": "Hololive Official",
    # Non-Gen
    "UC0TXe_LYZ4scaW2XMyi5_kw": "AZKi",
    "UC5CwaMl1eIgY8h02uZw7u8A": "Hoshimachi Suisei",
    "UCDqI2jOz0weumE8s7paEk6g": "Roboco-san",
    "UC-hM6YJuNYVAmUWxeIr9FeA": "Sakura Miko",
    "UCp6993wxpyDPHUpavwDFqgg": "Tokina Sora",
    # Gamers
    "UChAnqc_AY5_I3Px5dig3X1Q": "Inugami Korone",
    "UCvaTdHTWBGv3MKj3KVqJVCw": "Nekomata Okayu",
    "UCdn5BQ06XqgXoAxIhbqw5Rg": "Shirakami Fubuki",
    "UCp-5t9SrOQwXMU7iIjQfARg": "Okami Mio",
    # Gen 1
    "UC1CfXB_kRs3C-zaeTG3oGyg": "Akai Haato",
    "UCHj_mh57PVMXhAUDphUQDFA": "Akai Haato",  # Sub ch.
    "UCFTLzh12_nrtzqBPsTCqenA": "Aki Rosenthal",
    "UCQ0UDLQCjY0rmuxCDE38FGg": "Natsuiro Matsuri",
    "UCD8HOxPs4Xvsm8H0ZxXGiBw": "Yozora Mel",
    # Gen 2
    "UC1opHUrw8rvnsadT-iGp7Cg": "Minato Aqua",
    "UCXTpFs_3PqI41qX2d9tL2Rw": "Murasaki Shion",
    "UC7fk0CB07ly8oSl0aqKkqFg": "Nakiri Ayame",
    "UCvzGlP9oQwU--Y0r9id_jnA": "Oozora Subaru",
    "UC1suqwovbL1kzsoaZgFZLKg": "Yuzuki Choco",
    "UCp3tgHXw_HI0QMk1K8qh3gQ": "Yuzuki Choco",  # Sub ch.
    # Gen 3
    "UCCzUftO8KOVkV4wQG1vkUvg": "Houshou Marine",
    "UCvInZx9h3jC2JzsIzoOebWg": "Shiranui Flare",
    "UCdyqAaZDKHXg4Ahi7VENThQ": "Shirogane Noel",
    "UCl_gCybOJRIgOXw6Qb4qJzQ": "Uruha Rushia",
    "UC1DCedRgGHBdm81E1llLhOQ": "Usada Pekora",
    # Gen 4
    "UCZlDXzGoo7d44bwdNObFacg": "Amane Kanata",
    "UCa9Y57gfeY0Zro_noHRVrnw": "Himemori Luna",
    "UCS9uQI-jC3DE0L4IpXyvr6w": "Kiryu Coco",
    "UC1uv2Oq6kNxgATlCiez59hw": "Tokoyami Towa",
    "UCqm3BQLlJfvkTsX_hvm0UmA": "Tsunomaki Watame",
    # HoloID - Gen 1
    "UCOyYb1c43VlX9rc_lT6NKQw": ".HoloID/Ayunda Risu",
    "UCP0BspO_AMEe3aQqqpo89Dg": ".HoloID/Moona Hoshinova",
    "UCAoy6rzhSf4ydcYjJw3WoVg": ".HoloID/Airani Iofifteen",
}

vtlog.info("====================== Start of process! ======================")

STREAMLINK_CMD = [BASE_VENV_BIN + "streamlink", "-o"]
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
    dtnow = datetime.now().timestamp()
    with open(vthjs, "r") as fp:
        vt = json.load(fp)
    if vt["isDownloaded"]:
        vtlog.debug(
            "Skipping {}, reason: Already downloaded.".format(vt["id"])
        )
        continue
    if vt["isDownloading"]:
        vtlog.debug(
            "Skipping {}, reason: Currently downloading.".format(vt["id"])
        )
        continue
    if vt["isPaused"]:
        vtlog.debug("Skipping {}, reason: Currently paused.".format(vt["id"]))
        continue
    if vt["startTime"] > dtnow:
        vtlog.debug(
            "Skipping {}, reason: Still far away from scheduled time.".format(
                vt["id"]
            )
        )
        continue
    if dtnow > (vt["startTime"] + 300) and not vt["firstRun"]:
        vtlog.debug(
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
    vtlog.info("Undownloaded streams found, starting...")
    save_ts_name = (
        "'" + BASE_VTHELL_PATH + "streamdump/" + vt["filename"] + ".ts'"
    )

    vtlog.info("Starting job for: {}".format(vt["id"]))
    vtlog.debug("Output: {}".format(save_ts_name))
    STREAMLINK_CMD.extend([save_ts_name, vt["streamUrl"], "best"])
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
        if line.startswith("error"):
            if "read timeout" in line:
                override_err = True
            if "429 client error" in line:
                req_limit_err = True
            if "unrecognized arguments" in line:
                args_unk_err = True
        if "opening stream" in line:
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
    + " downloaded, will be muxed and uploaded."
)
vtlog.info(
    "Job {} download success, now muxing...".format(vthell_stream["id"])
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
                upload_mapping.get(vthell_stream["streamer"], "Unknown")
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
