# N4O VTuberHell Tools
**Created by**: N4O#8868

**Version**: 1.3
**Last Updated**: 07/04/2020

**Table of contents**:
- [Changelog](#user-content-what-s-changed)
    - [Version 1.3](#version-1-3-change)
- [Information](#user-content-info)
- [Requirements](#user-content-requirements)
- [Setup](#user-content-setup)
- [Running](#user-content-running)
    - [addjob.sh](#user-content-addjob-sh)
    - [runjob.sh](#user-content-runjob-sh)
    - [vtrip.sh](#user-content-vtrip-sh)
    - [vtup.sh](#user-content-vtup-sh)
- [Helper scripts](#user-content-helper-scripts)
    - [schedule.py](#user-content-schedule-py)
    - [vthell.py](#user-content-vthell-py)
    - [vtrip_helper.py](#user-content-vtrip-helper-sh)

### What's changed?
#### Version 1.3 Change:
- Reformatted python file with black.
- Added vtup.sh and vtrip.sh (+ vtrip_helper.py)
- Add more holovtuber support.

### Info
- All path are hardcoded, change accordingly
- datetime.now() on `vthell.py` originally on UTC+0/GMT, change accordingly
- No support for other Organization/Solo except Hololive (for now)
- Provide your own API Key for YouTube Data API v3
  - Used in `vtrip_helper.py` and `schedule.py`

### Requirements
- Linux based machine (I made this for my server in mind)
- Apps:
  - screen
  - mkvtoolnix
  - rclone (setup this for your cloud drive)

### Setup
0. Install requirements
1. Change all hardcoded path
2. Get YouTube Data API Key v3 from Cloud Console
3. Create `jobs` folder and `streamdump` folder
4. chmod all scripts (.sh)
5. Create venv python 3.5+ and install via pip
- requests
- pytz
- streamlink
6. Change the python from venv path on `addjob.sh` and `runjob.sh`

### Running
#### [addjob.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/addjob.sh)
**./addjob.sh** [youtube_link]

Supported youtube link format are:
- https://www.youtube.com/watch?v=VIDEOID
- https://youtu.be/VIDEOID

It will create a .json files containing some info that will be parsed by `runjob.sh` or `vthell.py`

Using **Youtube Data API v3** to determine output filename.
Please provide your **`API_KEY`** to the file.

**Output filename format**: `[YYYY.MM.DD] TITLE [RESOLUTIONp AAC].mkv`


#### [runjob.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/runjob.sh)
**./runjob.sh**

You can use **`cronjob`** to run every minute or whatever interval you want or run it manually.

It will check all `.json` in `jobs` folder and process the one that are not processed yet.

***What will be checked?*** the .json file
The json file contains 3 keys that will be used to check:
- **`startTime`** if the `startTime` not less than 2 minutes left, it will be skipped completely
- **`isDownloaded`** stream `finished`, and file is being muxed and will be uploaded.
- **`isDownloading`** will skip if True to `prevent double download`.

After **2 minutes left before stream**, it will use **streamlink** to check if stream online or not.
If not continue, if yes start recording.

After stream finished, file will be muxed into .mkv and will be uploaded, .ts file will be deleted and also the .json files.

**Recommended cron schedule:**
```sh
*/1 * * * * /path/to/vthell/runjob.sh
```


#### [vtrip.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/vtrip.sh)
**./vtrip.sh** [url]

Download your vtuber (mainly holo) video from youtube.
Doesn't support playlist.
Output format are: [YYYY.MM.DD] TITLE [RESOLUTION AAC].mkv
YYYY.MM.DD are Date uploaded or streamed.
Combine with `vtup.sh` later

[vtrip_helper.py](https://git.ihateani.me/noaione/vthell/src/branch/master/vtrip_helper.py) are helper to determine the output name using Youtube Data API v3.
Please provide your API_KEY to the file.

**Don't use this if you're ripping currently live streamed video, use addjob.sh for that**


#### [vtup.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/vtup.sh)
**./vtup.sh** "\[file]" \[vtuber] \[type]

Upload your **[file]** to the cloud drive.

allowed **[vtuber]**:
- holo
- azki
- suisei
- roboco
- miko
- sora
- korone
- okayu
- fubuki
- mio
- haato
- aki
- matsuri
- mel
- aqua
- shion
- ayame
- subaru
- choco
- marine
- flare
- noel
- rushia
- pekora
- kanata
- luna
- coco
- towa
- watame

allowed **[type]**:
- s: `for stream archive`
- stream: `for stream archive`
- archive: `for stream archive`
- cover: `for song cover`
- utaite: `for song cover`
- ani: `for animation`
- anime: `for animation`
- ori: `original songs`
- uta: `original songs`

if you put other stuff on **[vtuber]** or **[type]**
it will default to `Unknown`.


### Helper scripts
#### [schedule.py](https://git.ihateani.me/noaione/vthell/src/branch/master/schedule.py)
Script that will fetch provided youtube url a metadata that will be put on `jobs` folder.

Fetched stuff via API:
- Stream title (For output)
- Stream schedule start
- Streamer Channel ID

Everything will be saved into a json file containing information for `vthell.py` will use.

#### [vthell.py](https://git.ihateani.me/noaione/vthell/src/branch/master/vthell.py)
Main python script that will download the scheduled jobs
Download will start if the conditions are met:
- Stream started
- Stream hasn't yet been downloaded
- Stream is not being downloaded by other process.

It will start checking 2 minutes before stream start.

#### [vtrip_helper.py](https://git.ihateani.me/noaione/vthell/src/branch/master/vtrip_helper.py)
Literally a script to only find the video/stream title and make a output format for `youtube-dl`

*Licensed with MIT License*