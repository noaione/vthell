import argparse
import json
import logging
import os
import sys
import subprocess as sp

from chat_downloader import ChatDownloader
from chat_downloader.errors import (
    URLNotProvided,
    SiteNotSupported,
    LoginRequired,
    VideoUnavailable,
    NoChatReplay,
    VideoUnplayable,
    InvalidParameter,
    InvalidURL,
    RetriesExceeded,
    NoContinuation
)
from chat_downloader.output.continuous_write import ContinuousWriter

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

parser = argparse.ArgumentParser(prog="vtchat")
parser.add_argument("path", help="VTHell JSON Data")
parser.add_argument("-c", "--cookie", action="store", help="Path to cookies")
args = parser.parse_args()

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(
            os.path.join(BASE_VTHELL_PATH, "nvthell.log"), "a", "utf-8"
        )
    ],
    format="%(asctime)s %(name)-1s -- [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
vtlog = logging.getLogger("vtchat_archive")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.DEBUG)
console_formatter = logging.Formatter("[%(asctime)s][%(levelname)s]: %(message)s")
console.setFormatter(console_formatter)
vtlog.addHandler(console)

kwargs = {}
if args.cookie:
    kwargs["cookies"] = args.cookie

dataset_path = os.path.join(BASE_VTHELL_PATH, "dataset")

vtlog.info(f"Reading {args.path}")
with open(args.path, "r", encoding="utf-8") as fp:
    vthell_data = json.load(fp)

vtlog.info("Reading youtube_mapping")
with open(os.path.join(dataset_path, "_youtube_mapping.json")) as fp:
    upload_mapping = json.load(fp)

vtlog.info("Creating downloader class!")
downloader = ChatDownloader(**kwargs)
saving_path = os.path.join(BASE_VTHELL_PATH, "chatarchive")
if not os.path.exists(saving_path):
    os.makedirs(saving_path)

chat_file = os.path.join(saving_path, vthell_data["filename"] + ".chat.json")

vtlog.info(f"Opening new file at: {chat_file}")
output_file = ContinuousWriter(chat_file, indent=4)
try:
    vtlog.info(f"Starting archival process of {vthell_data['streamUrl']}")
    chatter = downloader.get_chat(url=vthell_data["streamUrl"])
    for chat in chatter:
        output_file.write(chat, flush=True)
except (
    URLNotProvided,
    SiteNotSupported,
    LoginRequired,
    VideoUnavailable,
    NoChatReplay,
    VideoUnplayable,
    InvalidParameter,
    InvalidURL,
    RetriesExceeded,
    NoContinuation
) as e:
    vtlog.warning("Got an error while trying to save chat")
    vtlog.error(e)
finally:
    downloader.close()
    output_file.close()

CHAT_FOLDER = "Stream Chat Archive"
STREAMER_PATH = upload_mapping.get(vthell_data["streamer"], {}).get(
    "upload_path", "Unknown"
)

if vthell_data["memberOnly"]:
    CHAT_FOLDER = "Member-Only " + CHAT_FOLDER

UPLOAD_PATH = os.path.join(RCLONE_TARGET_BASE, CHAT_FOLDER, STREAMER_PATH).replace("\\", "/")

UPLOAD_CMD = [RCLONE_PATH, "-v", "-P", "copy", chat_file, UPLOAD_PATH]

vtlog.info(f"{vthell_data['id']}: Uploading chat with rclone!")
sp.call(UPLOAD_CMD)
vtlog.info(f"{vthell_data['id']}: Cleaning up the file")

try:
    os.remove(chat_file)
except OSError:
    pass
