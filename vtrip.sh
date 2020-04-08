#!/bin/bash

if [ -z "$1" ]
then
    echo "Please provide a youtube link"
    exit 1
fi

URL="$1"
# Explain!
# 303+140: 1080p60 WEBM/VP9 + AAC 128kb/s
# 299+140: 1080p60 MP4/H264 + AAC 128kb/s
# 248+140: 1080p WEBM/VP9 + AAC 128kb/s
# 137+140: 1080p MP4/H264 + AAC 128kb/s
# 302+140: 720p60 WEBM/VP9 + AAC 128kb/s
# 298+140: 720p60 MP4/H264 + AAC 128kb/s
# 247+140: 720p WEBM/VP9 + AAC 128kb/s
# 136+140: 720p MP4/H264 + AAC 128kb/s
FORMAT="303+140/299+140/248+140/137+140/302+140/298+140/247+140/136+140"
YTDL_PATH="/media/sdac/mizore/pip3/bin/youtube-dl"
PY3_PATH="/media/sdac/mizore/pip3/bin/python3"

OUTPUT_FN=`${PY3_PATH} ./scripts/vtrip_helper.py ${URL}`

echo $OUTPUT_FN

$YTDL_PATH -f "$FORMAT" --merge-output-format mkv --all-subs --embed-subs --convert-subs ass -o "$OUTPUT_FN" $URL