<h1 align="center">
    <img src="https://cdn.discordapp.com/emojis/651022528785022976.png?v=1"><br>
    N4O VTuber Recording Tools
</h1>
<p align="center"><b>Version 1.7</b><br><i>A rabbit hole you shouldn't enter, once entered you can't get out.</i></p>
<p align="center">Created by: <b>N4O</b><br/>Last Updated: <b>15/04/2020</b></p>

**WARNING**<br>
Doesn't support anyone outside HoloLive currently. :^)<br>
You can still use it but when it's uploaded it will use `Unknown/Unknown` as the folder

**Table of Contents**:
- [Requirements](#requirements)
- [Setup](#setup)
    - [Setup python virtualenv](#setup-virtualenv)
    - [Setup rclone](#setup-rclone)
    - [Get "YouTube Data API v3" API key.](#get-youtube-data-api-v3-api-key)
    - **Optional** [Setup Discord Announcer](#setup-discord-announcer-optional)
    - [Setup VTHell](#setup-vthell)
    - [Configuring auto-scheduler](#configuring-auto-scheduler)
- [Running](#running)
    - [addjob.sh](#addjob-sh-https-git-ihateani-me-noaione-vthell-src-branch-master-addjob-sh)
    - [runjob.sh](#runjob-sh-https-git-ihateani-me-noaione-vthell-src-branch-master-runjob-sh)
    - [runauto.sh](#runauto-sh-https-git-ihateani-me-noaione-vthell-src-branch-master-runauto-sh)
    - [vtrip.sh](#vtrip-sh-https-git-ihateani-me-noaione-vthell-src-branch-master-vtrip-sh)
    - [vtup.sh](#vtup-sh-https-git-ihateani-me-noaione-vthell-src-branch-master-vtup-sh)
- [Troubleshooting](#troubleshooting)
- [Helpful `alias`](#helpful-bashrc-or-alias)

## Requirements
- Linux Server
- Python 3.5+
- screen
- mkvmerge
- rclone

**Python module:**
- requests
- pytz
- youtube-dl
- streamlink
- discord_webhook


## Setup
### Setup virtualenv
1. Install Python 3.5+ and `virtualenv`
2. Make a python virtualenv and install all the python module
    ```bash
    $ virtualenv vthellenv
    $ source vthellenv/bin/activate
    $ pip3 install -U requests pytz youtube-dl streamlink
    $ deactivate
    ```
    
### Setup rclone
1. Install `rclone`: https://rclone.org/install/
2. Setup `rclone` by refering to their [documentation](https://rclone.org/docs/)

A simple setup using google drive will be
```
$ rclone config
Current remotes:

Name                 Type
====                 ====

e) Edit existing remote
n) New remote
d) Delete remote
r) Rename remote
c) Copy remote
s) Set configuration password
q) Quit config
e/n/d/r/c/s/q>
```
- Type `n` for creating a new remote
```
e/n/d/r/c/s/q> n
name> [enter whatever you want]
```
- After that you will be asked to enter number/name of the storage<br>
Find `Google Drive` and type the number beside it.
```
Type of storage to configure.
Enter a string value. Press Enter for the default ("").
Choose a number from below, or type in your own value
[...]
12 / Google Cloud Storage (this is not Google Drive)
   \ "google cloud storage"
13 / Google Drive
   \ "drive"
14 / Google Photos
   \ "google photos"
[...]
Storage> 13
```
- When asked for `Google Application Client Id` just press enter.<br>
- When asked for `Google Application Client Secret` just press enter.<br>
- When asked for `scope` press `1` and then enter.<br>
- When asked for `root_folder_id` just press enter.<br>
- When asked for `service_account_file` just press enter.<br>
- When asked if you want to edit **advanced config** press `n` and enter.<br>
- When asked this:
```
Remote config
Use auto config?
 * Say Y if not sure
 * Say N if you are working on a remote or headless machine
y) Yes (default)
n) No
y/n>
```
Press `y` if you have GUI access, or `n` if you're using SSH/Console only.
If you use SSH/Console, you will be given a link, open it, authorize your<br>
account and copy the `verification code` result back to the console.<br><br>
If you use GUI it will open a browser and you can authorize it normally.<br>
When asked for `Configure this as a team drive?` just press `n` if you don't or `y` if you're using team drive.<br>
```
--------------------
[vthell]
type = drive
scope = drive
token = {"access_token":"REDACTED","token_type":"Bearer","refresh_token":"REDACTED","expiry":"2020-04-12T11:07:42.967625371Z"}
--------------------
y) Yes this is OK (default)
e) Edit this remote
d) Delete this remote
y/e/d>
```
- Press `y` to complete the setup or `e` if you want to edit it again.<br>
- You can exit by typing `q` and enter after this.

### Get "YouTube Data API v3" API key.
1. Go to: https://console.developers.google.com/
2. Create a new project
3. Go to: `APIs & Services` ~> `Library`
4. Search: `YouTube Data API v3` and click it
5. Enable the API, and wait
6. Click `Manage` on the same page after your API is enabled, if you can't see it, try refreshing it.
7. Go to `Credentials`
8. Click `+ Create Credentials` ~> `API key`
9. Copy and save it somewhere save for now.
10. Click `Close`
11. From the API key you saved before, create a new ENV key on your linux machine, titled: `VTHELL_YT_API_KEY`<br>
    You can edit your `${HOME}/.profile` file and add this:
    ```
    VTHELL_YT_API_KEY="YOUR_API_KEY"; export VTHELL_YT_API_KEY
    ```

### Setup Discord Announcer (OPTIONAL)
1. Setup a new channel in your discord server
2. Click the gear icon (Edit channel) beside the channel name
3. Click `Webhooks` then `Create Webhook`
4. Name it whatever you want and copy the webhook URL
5. With the same step as `Step 11` from [Get “YouTube Data API v3” API key.](#get-youtube-data-api-v3-api-key), you need to made a ENV key<br>
    You can edit your `${HOME}/.profile` file and add this:
    ```
    VTHELL_DISCORD_WEBHOOK="DISCORD_WEBHOOK_URL"; export VTHELL_DISCORD_WEBHOOK
    ```

### Setup VTHell
1. Download or clone this repository
2. Create `jobs` and `streamdump` folder inside vthell folder<br>
    Example:
    ```
    $ ls -alh ~/vthell/
    drwxr-xr-x  6 mizore mizore 4.0K Apr 12 04:27 .
    drwx------ 27 mizore mizore 4.0K Apr 12 08:57 ..
    -rwxr--r--  1 mizore mizore  176 Apr  9 03:51 addjob.sh
    drwxr-xr-x  2 mizore mizore 4.0K Apr 12 10:12 jobs
    -rwxr--r--  1 mizore mizore  102 Apr 12 04:27 runauto.sh
    -rwxr--r--  1 mizore mizore  113 Apr  9 03:51 runjob.sh
    drwxr-xr-x  2 mizore mizore 4.0K Apr 12 08:59 scripts
    drwxr-xr-x  2 mizore mizore 4.0K Apr 12 09:00 streamdump
    -rwxr--r--  1 mizore mizore  982 Apr 11 08:39 vtrip.sh
    -rwxr--r--  1 mizore mizore 4.0K Apr  8 02:21 vtup.sh
    ```
3. Change all of this part

**In `scripts/schedule.py`**<br>
```py
BASE_VTHELL_PATH = (
    "/media/sdac/mizore/vthell/"  # Absoule path to vthell folder
)
```
Change `BASE_VTHELL_PATH` to the absolute path of your vthell folder

**In `scripts/vtauto_schedule.py`**<br>
```py
BASE_VTHELL_PATH = "/media/sdac/mizore/vthell/"  # Absoule path to vthell folder
```
Change `BASE_VTHELL_PATH` to the absolute path of your vthell folder

**In `scripts/vthell.py`**<br>
```py
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
```
Change `BASE_VTHELL_PATH` to the absolute path of your vthell folder<br><br>
Change `RCLONE_PATH` to where you put your rclone file, you can find it with
```bash
$ which rclone
```
if you install it systemwide<br><br>
Change `RCLONE_TARGET_BASE` to what you configured before with `rclone config`<br>
`naomeme` is your drive name that you use<br>
`Backup/VTuberHell/` is your folder you want to use.<br>
So if you want to change it to drive `foo` and folder `VTuberBackup`: `foo:VTuberBackup/`<br><br>
Change `BASE_VENV_BIN` to where you setup your `virtualenv` folder, target it to the `bin` folder that contain stuff like this:
```bash
$ ls -alh ~/pip3/bin/
total 4.7M
drwx------ 3 REDACTED REDACTED 4.0K Apr  8 13:59 .
drwx------ 7 REDACTED REDACTED 4.0K Apr  4 23:26 ..
-rw------- 1 REDACTED REDACTED 2.2K Apr  4 10:03 activate
-rw------- 1 REDACTED REDACTED 1.4K Apr  4 10:03 activate.csh
-rw------- 1 REDACTED REDACTED 3.1K Apr  4 10:03 activate.fish
-rw------- 1 REDACTED REDACTED 1.8K Apr  4 10:03 activate.ps1
-rw------- 1 REDACTED REDACTED 1.5K Apr  4 10:03 activate_this.py
-rw------- 1 REDACTED REDACTED 1.2K Apr  4 10:03 activate.xsh
-rwxr-xr-x 1 REDACTED REDACTED  240 Apr  4 10:04 chardetect
-rwxr-xr-x 1 REDACTED REDACTED  242 Apr  8 13:59 discord_webhook
-rwxr-xr-x 1 REDACTED REDACTED  249 Apr  4 10:03 easy_install
-rwxr-xr-x 1 REDACTED REDACTED  249 Apr  4 10:03 easy_install-3.5
-rwxr-xr-x 1 REDACTED REDACTED  240 Apr  4 10:03 pip
-rwxr-xr-x 1 REDACTED REDACTED  240 Apr  4 10:03 pip3
-rwxr-xr-x 1 REDACTED REDACTED  240 Apr  4 10:03 pip3.5
lrwxrwxrwx 1 REDACTED REDACTED    7 Apr  4 10:02 python -> python3
-rwxr-xr-x 1 REDACTED REDACTED 4.6M Apr  4 10:02 python3
lrwxrwxrwx 1 REDACTED REDACTED    7 Apr  4 10:02 python3.5 -> python3
-rwxr-xr-x 1 REDACTED REDACTED 2.3K Apr  4 10:03 python-config
-rwxr-xr-x 1 REDACTED REDACTED  237 Apr  4 10:05 streamlink
-rwxr-xr-x 1 REDACTED REDACTED  227 Apr  4 10:03 wheel
-rwx--x--x 1 REDACTED REDACTED 6.3K Apr  4 10:05 wsdump.py
-rwxr-xr-x 1 REDACTED REDACTED  228 Apr  4 23:26 youtube-dl
```

**In most of the bash file**<br>
Change `/media/sdac/mizore/pip3/bin/python3` to your virtualenv python
Change `/media/sdac/mizore/vthell/scripts` to your absolute path of your vthell scripts folder

**In `vtrip.sh`**<br>
Change this:
```bash
YTDL_PATH="/media/sdac/mizore/pip3/bin/youtube-dl"
PY3_PATH="/media/sdac/mizore/pip3/bin/python3"
VTHELL_PATH="/media/sdac/mizore/vthell"
```
Set the `YTDL_PATH` to your `youtube-dl` in virtualenv `bin` folder
Set the `PY3_PATH` to your `python3` in virtualenv `bin` folder
Set the `VTHELL_PATH` to your absolute path of your vthell folder

**In `vtup.sh`**<br>
Change this:
```bash
BASE_TARGET="naomeme:Backup/VTuberHell"
RCLONE_PATH="/media/sdac/mizore/bin/rclone"
```
Set the `RCLONE_PATH` to where you put your rclone file, you can find it with
```bash
$ which rclone
```
if you install it systemwide<br><br>
Change `BASE_TARGET` to what you configured before with `rclone config`<br>
`naomeme` is your drive name that you use<br>
`Backup/VTuberHell/` is your folder you want to use.<br>
So if you want to change it to drive `foo` and folder `VTuberBackup`: `foo:VTuberBackup/`

3. You're mostly ready to use this """program"""


### Configuring auto-scheduler
**Main file: [scripts/vtauto_schedule.py](https://git.ihateani.me/noaione/vthell/src/branch/master/scripts/vtauto_schedule.py)**

There's 2 main part to edit, `ENABLED_MAP` and `IGNORED_MAP`<br>
`ENABLED_MAP` are streams that will be scheduled if it match one of the defined conditions.<br>
While `IGNORED_MAP` will remove anything that match the conditions.

The default one for `ENABLED_MAP` are:
- Towa ch.
- Korone ch.
- Any title containing: `歌う`
- Any title containing: `歌枠`

The default one for `IGNORED_MAP` are:
- All HoloStars Channel
- Any title containing: `(cover)`
- Any title containing: `あさココ`

There's only 2 supported `type` now:
- `channel`
- `word`

`channel` will record/ignore any upcoming live from the `channel`<br>
`word` will record/ignore any upcoming live when the title have the certain `word`

Example:
```json
{"type": "word", "data": "歌う"}
```
Record anything that have `歌う` (utau) in the title

```json
{"type": "channel", "data": "UC1uv2Oq6kNxgATlCiez59hw"}
```
Record anything from `channel`: `UC1uv2Oq6kNxgATlCiez59hw` (`UC1uv2Oq6kNxgATlCiez59hw` are channel ID)<br>
Channel ID for other HoloLiver are provided in `MAPPING` variable

You can add more by just creating a new line after the last one.<br>
You also can remove any predefined one if you want.

## Running
#### [addjob.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/addjob.sh)
**./addjob.sh** [youtube_link1] [youtube_link2] [youtube_link_etc]

Supported youtube link format are:
- https://www.youtube.com/watch?v=VIDEOID
- https://youtu.be/VIDEOID

It will create a .json files containing some info that will be parsed by `runjob.sh` or `vthell.py`

Using **Youtube Data API v3** to determine output filename.<br>
**Output filename format**: `[YYYY.MM.DD] TITLE [RESOLUTIONp AAC].mkv`

#### [runjob.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/runjob.sh)
**./runjob.sh**

You can use **`cronjob`** to run every minute or whatever interval you want or run it manually.

It will check all `.json` in `jobs` folder and process the one that are not processed yet.

***What will be checked?*** the .json file<br>
The json file contains 3 keys that will be used to check:
- **`startTime`** if the `startTime` not less than 2 minutes left, it will be skipped completely
- **`isDownloaded`** stream `finished`, and file is being muxed and will be uploaded.
- **`isDownloading`** will skip if True to `prevent double download`.

After **2 minutes left before stream**, it will use **streamlink** to check if stream online or not.<br>
If not continue, if yes start recording.

After stream finished, file will be muxed into .mkv and will be uploaded, .ts file will be deleted and also the .json files.

**Recommended cron schedule:**
```sh
*/1 * * * * /path/to/vthell/runjob.sh
```

#### [runauto.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/runauto.sh)
**./runauto.sh**

You can use **`cronjob`** to run every 3 minute or whatever interval you want or run it manually.

It will fetch to [HoloLive Jetri](https://hololive.jetri.co/) endpoint to get upcoming live and ongoing live.<br>
It will add whatever in `ENABLED_MAP` variable, like channel or certain words in a title.<br>
You can add what you don't want to `IGNORED_MAP` variable.<br>
After that, it will check all `.json` in `jobs` folder and add the one that are not exist yet.

**To customize refer to: [Configuring auto-scheduler](#configuring-auto-scheduler)**

**Recommended cron schedule:**
```sh
*/3 * * * * /path/to/vthell/runauto.sh
```

#### [vtrip.sh](https://git.ihateani.me/noaione/vthell/src/branch/master/vtrip.sh)
**./vtrip.sh** [url]

Download your vtuber (mainly holo) video from youtube.<br>
Doesn't support playlist.<br>
Output format are: [YYYY.MM.DD] TITLE [RESOLUTION AAC].mkv<br>
YYYY.MM.DD are Date uploaded or streamed.<br>
Combine with `vtup.sh` later

[vtrip_helper.py](https://git.ihateani.me/noaione/vthell/src/branch/master/scripts/vtrip_helper.py) are helper to determine the output name using Youtube Data API v3.

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
- c: `for stream clips`
- clips: `for stream clips`
- cover: `for song cover`
- utaite: `for song cover`
- ani: `for animation`
- anime: `for animation`
- ori: `original songs`
- uta: `original songs`

if you put other stuff on **[vtuber]** or **[type]**
it will default to `Unknown`.


## Troubleshooting
> Stream xxxxxx are paused

Enable it again when the VTuber start streaming by using `./addjob.sh [youtube_link]`

> Error 429

You're rate limited by YouTube there's nothing you can't do except using proxy temporarily

> "Please add Niji ID VTuber or other VTuber"

If someone want to actually compile a list containing every channel ID of the VTuber, I'll add it.<br>
**You can contact me at Discord: N4O#8868**

> "I added DISCORD_WEBHOOK to my ENV key but I'm not getting any announcement"

Replace the `DISCORD_WEBHOOK_URL = os.getenv("VTHELL_DISCORD_WEBHOOK", "")` with<br>
```py
DISCORD_WEBHOOK_URL = "YOUR_WEBHOOK_URL"
```

## Helpful `.bashrc` or `alias`
> Shortcut for `addjob.sh`
```bash
alias vta="/path/to/vthell/addjob.sh"
```

> Shortcut for `runjob.sh`
```bash
alias vtr="/path/to/vthell/runjob.sh"
```

> Shortcut for `runauto.sh`
```bash
alias vtar="/path/to/vthell/runauto.sh"
```

> Shortcut for `vtrip.sh`
```bash
alias vtd="/path/to/vthell/vtrip.sh"
```

> Shortcut for `vtup.sh`
```bash
alias vtu="/path/to/vthell/vtup.sh"
```

> Follow logfile
```bash
alias vtl="tail -f -n 80 /path/to/vthell/nvthell.log"
```

> See all the jobs<br>
**WARNING**: You need `jq` in your PATH
```bash
alias vtj='for jobs in /path/to/vthell/jobs/*.json; do jname=`cat $jobs | jq -r '.filename'`; jsurl=`cat $jobs | jq -r '.streamUrl'`; jsdling=`cat $jobs | jq '.isDownloading'`; jsdled=`cat $jobs | jq '.isDownloaded'`; jdtime=`cat $jobs | jq '.startTime'`; jdtime="$(($jdtime + 28800))"; jdtime=`date -d @$jdtime`; printf "Title: ${jname}\nLink: ${jsurl}\nStart Time: ${jdtime/UTC/UTC+7}\nDownloading? ${jsdling^}   Downloaded? ${jsdled^}\n\n"; done'
```