#!/bin/bash

if [ -z "$1" ]
then
    echo "Please provide a youtube link"
    exit 1
fi

/media/sdac/mizore/pip3/bin/python3 /media/sdac/mizore/vthell/scripts/schedule.py "$1"
