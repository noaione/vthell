#!/media/sdac/mizore/pip3/bin/python3

import os
import re
import sys
from datetime import datetime

import pytz
import requests

API_KEY = os.getenv("VTHELL_YT_API_KEY", "")
if not API_KEY:
    print("Please provide VTHELL_YT_API_KEY to the environment.")
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

s = requests.get(BASE_YT_URL.format(input_url, API_KEY))
if s.status_code != 200:
    print("Failed fetching title")
    exit(1)
res = s.json()
snippets = res["items"][0]["snippet"]
if "liveStreamingDetails" in res["items"][0]:
    if "actualStartTime" in res["items"][0]["liveStreamingDetails"]:
        stream_start = res["items"][0]["liveStreamingDetails"][
            "actualStartTime"
        ]
    else:
        stream_start = res["items"][0]["liveStreamingDetails"][
            "scheduledStartTime"
        ]
else:
    stream_start = snippets["publishedAt"]
dts = datetime.strptime(stream_start, "%Y-%m-%dT%H:%M:%S.%fZ")
dts_ts = dts.timestamp() + 28800
dts_new = datetime.fromtimestamp(dts_ts).strftime("[%Y.%m.%d")
title = snippets["title"]
final_filename = "{}.{}] {}".format(dts_new, input_url, title)
final_filename += r" [%(height)dp AAC].%(ext)s"
final_filename = secure_filename(final_filename)
print(final_filename)
