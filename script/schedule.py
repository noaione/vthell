import argparse
import re

import requests

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", help="Port to connect to", type=int, default=12790)
parser.add_argument("-P", "--password", help="Password to connect to the server")
parser.add_argument("video", help="Video URL to schedule")
args = parser.parse_args()


def extract_video_id(url: str):
    """
    Get the video ID from the video name
    :param url: The video URL
    :return: Video ID
    """
    part = re.sub(r"http(?:s|)\:\/\/(?:www.|)youtu(?:.be|be\.com)\/", "", url)
    return re.sub(r"watch\?v\=", "", part)


headers = {
    "Authorization": f"Password {args.password}",
}
print(f"[*] Trying to schedule {args.video}")
resp = requests.post(
    f"http://localhost:{args.port}/api/schedule", json={"id": extract_video_id(args.video)}, headers=headers
)

if resp.status_code != 200:
    print(f"[!] Error scheduling video: {resp.text}")
    exit(1)

print(f"[*] Video {args.video} scheduled successfully")
