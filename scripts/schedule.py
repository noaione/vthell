import json
import re
import sys
from datetime import datetime

import pytz
import requests

BASE_VTHELL_PATH = (
    "/media/sdac/mizore/vthell/"  # Absoule path to vthell folder
)

API_KEY = ""
BASE_API = "https://www.googleapis.com/youtube/v3/"
BASE_YT_URL = BASE_API + "videos?id={}&key={}"
BASE_YT_URL += "&part=snippet%2Cstatus%2CliveStreamingDetails%2CcontentDetails"


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
    return fn


input_url = sys.argv[1]
input_url = re.sub(
    r"http(?:s|)\:\/\/(?:www.|)youtu(?:.be|be\.com)\/", "", input_url
)
input_url = re.sub(r"watch\?v\=", "", input_url)

dnow = datetime.now(pytz.timezone("Asia/Tokyo"))
dd_fn = dnow.strftime("[%Y.%m.%d]")

print("Scheduling: {}".format(input_url))
s = requests.get(BASE_YT_URL.format(input_url, API_KEY))
if s.status_code != 200:
    print("Failed fetching title")
    exit(1)
res = s.json()
snippets = res["items"][0]["snippet"]
stream_start = res["items"][0]["liveStreamingDetails"]["scheduledStartTime"]
dts = datetime.strptime(stream_start, "%Y-%m-%dT%H:%M:%S.%fZ")
dts_ts = dts.timestamp()
title = snippets["title"]
final_filename = "{} {} [1080p AAC]".format(dd_fn, title)
final_filename = secure_filename(final_filename)

print("Saving info to file...")
with open(BASE_VTHELL_PATH + "jobs/" + input_url + ".json", "w") as fp:
    json.dump(
        {
            "id": input_url,
            "filename": final_filename,
            "isDownloading": False,
            "isDownloaded": False,
            "startTime": dts_ts - 120,  # T-2
            "streamer": snippets["channelId"],
            "streamUrl": "https://www.youtube.com/watch?v=" + input_url,
        },
        fp,
        indent=2,
    )

print("Stream Scheduled!")
