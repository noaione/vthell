#!/bin/bash

if [ -z "$1" ]
then
    echo "Please provide a file to upload"
    exit 1
fi

if [ -z "$2" ]
then
    echo "Please provide a target folder"
    exit 1
fi

if [ -z "$3" ]
then
    echo "Please provide a type upload"
    exit 1
fi

FILE_TO_UP="$1"
TARGET_FOLDER="$2"
TYPE_UPLOAD="$3"

BASE_TARGET="naomeme:Backup/VTuberHell"
RCLONE_PATH="/media/sdac/mizore/bin/rclone"

case $TYPE_UPLOAD in
    s)
        BASE_TARGET="${BASE_TARGET}/Stream Archive"
        ;;
    stream)
        BASE_TARGET="${BASE_TARGET}/Stream Archive"
        ;;
    archive)
        BASE_TARGET="${BASE_TARGET}/Stream Archive"
        ;;
    c)
        BASE_TARGET="${BASE_TARGET}/Clips"
        ;;
    clips)
        BASE_TARGET="${BASE_TARGET}/Clips"
        ;;
    translatedclips)
        BASE_TARGET="${BASE_TARGET}/Clips"
        ;;
    cover)
        BASE_TARGET="${BASE_TARGET}/Cover Songs"
        ;;
    utaite)
        BASE_TARGET="${BASE_TARGET}/Cover Songs"
        ;;
    ani)
        BASE_TARGET="${BASE_TARGET}/Animation"
        ;;
    anime)
        BASE_TARGET="${BASE_TARGET}/Animation"
        ;;
    ori)
        BASE_TARGET="${BASE_TARGET}/Original Songs"
        ;;
    uta)
        BASE_TARGET="${BASE_TARGET}/Original Songs"
        ;;
    *)
        BASE_TARGET="${BASE_TARGET}/Unknown"
        ;;
esac

case $TARGET_FOLDER in
    holo)
        BASE_TARGET="${BASE_TARGET}/Hololive Official"
        ;;
    azki)
        BASE_TARGET="${BASE_TARGET}/AZKi"
        ;;
    sui)
        BASE_TARGET="${BASE_TARGET}/Hoshimachi Suisei"
        ;;
    suisei)
        BASE_TARGET="${BASE_TARGET}/Hoshimachi Suisei"
        ;;
    rbc)
        BASE_TARGET="${BASE_TARGET}/Roboco-san"
        ;;
    roboco)
        BASE_TARGET="${BASE_TARGET}/Roboco-san"
        ;;
    miko)
        BASE_TARGET="${BASE_TARGET}/Sakura Miko"
        ;;
    sora)
        BASE_TARGET="${BASE_TARGET}/Tokina Sora"
        ;;
    korone)
        BASE_TARGET="${BASE_TARGET}/Inugami Korone"
        ;;
    okayu)
        BASE_TARGET="${BASE_TARGET}/Nekomata Okayu"
        ;;
    fbk)
        BASE_TARGET="${BASE_TARGET}/Shirakami Fubuki"
        ;;
    fubuki)
        BASE_TARGET="${BASE_TARGET}/Shirakami Fubuki"
        ;;
    mio)
        BASE_TARGET="${BASE_TARGET}/Okami Mio"
        ;;
    haato)
        BASE_TARGET="${BASE_TARGET}/Akai Haato"
        ;;
    aki)
        BASE_TARGET="${BASE_TARGET}/Aki Rosenthal"
        ;;
    matsuri)
        BASE_TARGET="${BASE_TARGET}/Natsuiro Matsuri"
        ;;
    mel)
        BASE_TARGET="${BASE_TARGET}/Yozora Mel"
        ;;
    aqua)
        BASE_TARGET="${BASE_TARGET}/Minato Aqua"
        ;;
    shion)
        BASE_TARGET="${BASE_TARGET}/Murasaki Shion"
        ;;
    ayame)
        BASE_TARGET="${BASE_TARGET}/Nakiri Ayame"
        ;;
    subaru)
        BASE_TARGET="${BASE_TARGET}/Oozora Subaru"
        ;;
    choco)
        BASE_TARGET="${BASE_TARGET}/Yuzuki Choco"
        ;;
    marine)
        BASE_TARGET="${BASE_TARGET}/Houshou Marine"
        ;;
    flare)
        BASE_TARGET="${BASE_TARGET}/Shiranui Flare"
        ;;
    noel)
        BASE_TARGET="${BASE_TARGET}/Shirogane Noel"
        ;;
    rushia)
        BASE_TARGET="${BASE_TARGET}/Uruha Rushia"
        ;;
    peko)
        BASE_TARGET="${BASE_TARGET}/Usada Pekora"
        ;;
    pekora)
        BASE_TARGET="${BASE_TARGET}/Usada Pekora"
        ;;
    kanata)
        BASE_TARGET="${BASE_TARGET}/Amane Kanata"
        ;;
    ppt)
        BASE_TARGET="${BASE_TARGET}/Amane Kanata"
        ;;
    pptenshi)
        BASE_TARGET="${BASE_TARGET}/Amane Kanata"
        ;;
    luna)
        BASE_TARGET="${BASE_TARGET}/Himemori Luna"
        ;;
    coco)
        BASE_TARGET="${BASE_TARGET}/Kiryu Coco"
        ;;
    towa)
        BASE_TARGET="${BASE_TARGET}/Tokoyami Towa"
        ;;
    watame)
        BASE_TARGET="${BASE_TARGET}/Tsunomaki Watame"
        ;;
    *)
        BASE_TARGET="${BASE_TARGET}/Unknown"
        ;;
esac

echo $BASE_TARGET

$RCLONE_PATH -v -P copy "${FILE_TO_UP}" "${BASE_TARGET}"