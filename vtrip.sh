#!/bin/bash

URL="$1"
FORMAT="303+140/299+140/248+140/137+140/302+140/298+140/247+140/136+140"
YTDL_PATH="/media/sdac/mizore/pip3/bin/youtube-dl"
PY3_PATH="/media/sdac/mizore/pip3/bin/python3"

OUTPUT_FN=`${PY3_PATH} ./vtrip_helper.py ${URL}`

echo $OUTPUT_FN

$YTDL_PATH -f "$FORMAT" --merge-output-format mkv -o "$OUTPUT_FN" $URL