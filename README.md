<h1 align="center">
    <img src="https://media.discordapp.net/attachments/558322816995426305/687238504190574598/CocoOkite.gif"><br>
    N4O VTuber Recording Tools
</h1>
<p align="center"><b>Version 2.1</b><br><i>A rabbit hole you shouldn't enter, once entered you can't get out.</i></p>
<p align="center">Created by: <b>N4O</b><br/>Last Updated: <b>08/05/2020</b></p>
<p align="center"><a href="https://github.com/noaione/vthell/releases"><strong>Download</strong></a></p>

**Table of Contents**:
- [Information](#information)
- [Requirements](#requirements)
- [Setup](#setup)
    - [Setup python virtualenv](#setup-virtualenv)
    - [Setup rclone](#setup-rclone)
    - [Get "YouTube Data API v3" API key.](#get-youtube-data-api-v3-api-key)
    - **Optional** [Setup Discord Announcer](#setup-discord-announcer-optional)
    - [Setup VTHell](#setup-vthell)
    - [Configuring auto-scheduler](#configuring-auto-scheduler)
    - [Configuring twitcasting](#configuring-twitcasting)
- [Running](#running)
    - [addjob.sh](#addjobsh)
    - [runjob.sh](#runjobsh)
    - [runauto.sh](#runautosh)
    - [runtwit.sh](#runtwitsh)
    - [vtrip.sh](#vtripsh)
    - [vtup.sh](#vtupsh)
- [Troubleshooting](#troubleshooting)
- [Helpful `alias`](#helpful-bashrc-or-alias)

## Information
~~This tools currently doesn't support anyone else beside HoloLive.~~
<br>
~~You are able to use it but it will not work 100% or the upload mapping will be kinda fucked.~~
<br>
~~To be honest, this tools works for every livestream in YouTube. It will only be broken when the stream is recorded and will be uploaded.~~

**This program now support Agency outside Hololive, you can check it on [dataset](https://github.com/noaione/vthell/tree/master/dataset) folder.**

I only fully support Linux for now because Windows is annoying to make this fully automatic and I'm lazy to write up the tutorial.

This tools also utilize [HoloLive Tools](https://hololive.jetri.co/) API and YouTube Data API v3 for YouTube streams.<br>
And utilize twitcasting API for the twitcasting streams.

If you want to see other VLiver to be added to this list, you can contact me at **Discord: N4O#8868**<br>
I'll try to add it to this program.

This tools is not modular yet, but once it setup you can just use it easily.

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
    $ pip3 install -U requests pytz youtube-dl streamlink discord_webhook
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
1. [Download](https://github.com/noaione/vthell/releases) or [clone](https://api.github.com/repos/noaione/vthell/zipball/master) this repository
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

**In `scripts/vthell.py` AND In `scripts/twitcast.py`**<br>
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

[...]

"""
Cookies must be Netscape format or the one that can be opened with CURL.

Netscape format:
URL  INCLUDE_SUBDOMAINS  PATH  HTTPS_ONLY  EXPIRES  COOKIES_NAME  COOKIES_VALUE
.youtube.com  TRUE  /  TRUE  0  SAMPLES  SAMPLEVALUES
"""
COOKIES_NAME = "cookies.txt"  # Your cookies file name
```

**Update 1.9**<br>
This update introduce cookies support to be able to record member-only stream.<br>
Change `COOKIES_NAME` to your cookies that you put on the main vthell folder.

**WARNING**<br>
I only support Netscape format as seen on that top sample.

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
**Main file: [scripts/vtauto_schedule.py](https://github.com/noaione/vthell/blob/master/scripts/vtauto_schedule.py)**<br>
**[dataset/_auto_scheduler.json](https://github.com/noaione/vthell/blob/master/dataset/_auto_scheduler.json)**

**Update 2.0**
<br>
This update separate the mapping to it's own file, to edit if you want to enable Nijisanji or Hololive<br>
you can refer to the `vtauto_schedule.py` file.

While the `dataset/_auto_scheduler.json` contain what you want to allowed (enabled) or ignored (disabled).<br>
The format are still the same as before, you can still follow the instructions below.

**Update 1.9**
<br>
This update introduce Nijisanji to the auto uploader, you can enable/disable it on the main file.
```py
"""
Set to True or False if you want it to be processed/scheduled automatically

Default:
- Enable Hololive
- Disable Nijisanji
So, it will process Hololive but skip Nijisanji completely.
"""
PROCESS_HOLOLIVE = True
PROCESS_NIJISANJI = False
```

There's 2 main part to edit, `enabled` and `disabled`<br>
`enabled` are streams that will be scheduled if it match one of the defined conditions.<br>
While `IGNORED_MAP` will remove anything that match the conditions.

The default one for `enabled` are:
- Towa ch.
- Korone ch.
- Any title containing: `歌う`
- Any title containing: `歌枠`
- Any title containing: `歌雑談`
- Any title containing: `ASMR`
- Any title containing: `うたうよ`

The default one for `disabled` are:
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
Channel ID are provided in dataset folder.

You can add more by just creating a new line after the last one.<br>
You also can remove any predefined one if you want.

### Configuring Twitcasting
**Main file: [scripts/twitcast.py](https://github.com/noaione/vthell/blob/master/scripts/twitcast.py)**

**NOTE**<br>
I need help expanding the twitcast user ID, please contact me at Discord: N4O#8868

There's only 1 part you need to edit: `ENABLED_USERS` variable<br>

The default one enabled are:
- natsuiromatsuri

You only need to add the user ID to the `ENABLED_USERS` lists<br>
You can check the User ID on `upload_mapping` variable.

## Running
#### [addjob.sh](https://github.com/noaione/vthell/blob/master/addjob.sh)
**./addjob.sh** [youtube_link1] [youtube_link2] [youtube_link_etc]

Supported youtube link format are:
- https://www.youtube.com/watch?v=VIDEOID
- https://youtu.be/VIDEOID

It will create a .json files containing some info that will be parsed by `runjob.sh` or `vthell.py`

Using **Youtube Data API v3** to determine output filename.<br>
**Output filename format**: `[YYYY.MM.DD] TITLE [RESOLUTIONp AAC].mkv`

#### [runjob.sh](https://github.com/noaione/vthell/blob/master/runjob.sh)
**./runjob.sh**

You can use **`cronjob`** to run every minute or whatever interval you want or run it manually.

It will check all `.json` in `jobs` folder and process the one that are not processed yet.

***What will be checked?*** the .json file<br>
The json file contains 3 keys that will be used to check:
- **`startTime`** if the `startTime` not less than 2 minutes left, it will be skipped completely
- **`isDownloaded`** stream `finished`, and file is being muxed and will be uploaded.
- **`isDownloading`** will skip if True to `prevent double recording`.

After **1 minutes left before stream**, it will use **streamlink** to check if stream online or not.<br>
If not continue, if yes start recording.

After stream finished, file will be muxed into .mkv and will be uploaded, .ts file will be deleted and also the .json files.

**Recommended cron schedule:**
```sh
*/1 * * * * /path/to/vthell/runjob.sh
```

#### [runauto.sh](https://github.com/noaione/vthell/blob/master/runauto.sh)
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

#### [runtwit.sh](https://github.com/noaione/vthell/blob/master/runtwit.sh)
**./runtwit.sh**

You can use **`cronjob`** to run every 2 minute or whatever interval you want or run it manually.

It will fetch to Twitcasting frontend API endpoint to check if `ENABLED_USERS` are live or not.<br>
If it's it will add a "LOCK" file to jobs folder to ensure that no duplicate will be added.<br>
After it finish, it will unlock again the file and the final file will be uploaded.<br>

**To customize refer to: [Configuring auto-scheduler](#configuring-twitcasting)**

**Recommended cron schedule:**
```sh
*/2 * * * * /path/to/vthell/runtwit.sh
```

#### [vtrip.sh](https://github.com/noaione/vthell/blob/master/vtrip.sh)
**./vtrip.sh** [url]

Download your vtuber (mainly holo) video from youtube.<br>
Doesn't support playlist.<br>
Output format are: `[YYYY.MM.DD] TITLE [RESOLUTION AAC].mkv`<br>
YYYY.MM.DD are Date uploaded or streamed.<br>
Combine with `vtup.sh` later

[vtrip_helper.py](https://github.com/noaione/vthell/blob/master/scripts/vtrip_helper.py) are helper to determine the output name using Youtube Data API v3.

**Don't use this if you're ripping currently live streamed video, use addjob.sh for that**

#### vtup.sh
**REMOVED**

`vtup.sh` are now removed since version 1.9 since it's support more Agency.


## Troubleshooting
> Stream xxxxxx are paused

Enable it again when the VTuber start streaming by using `./addjob.sh [youtube_link]`

> Error 429

You're being rate limited by YouTube there's nothing you can do except using proxy temporarily

> "Please add VTuber from xxx."

If you want me to add that VTuber into the list, please help me compile them with the same format as most `dataset` list.<br>
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

> Follow logfile
```bash
alias vtl="tail -f -n 80 /path/to/vthell/nvthell.log"
```

> See all the jobs<br>
**WARNING**: You need `jq` in your PATH
```bash
alias vtj='for jobs in /path/to/vthell/jobs/*.json; do jname=`cat $jobs | jq -r '.filename'`; jsurl=`cat $jobs | jq -r '.streamUrl'`; jsdling=`cat $jobs | jq '.isDownloading'`; jsdled=`cat $jobs | jq '.isDownloaded'`; jdtime=`cat $jobs | jq '.startTime'`; jdtime="$(($jdtime + 32400))"; jdtime=`date -d @$jdtime`; printf "Title: ${jname}\nLink: ${jsurl}\nStart Time: ${jdtime/UTC/JST}\Recording? ${jsdling^}   Recorded? ${jsdled^}\n\n"; done'
```<h1 align="center">
    <img src="https://media.discordapp.net/attachments/558322816995426305/687238504190574598/CocoOkite.gif"><br>
    N4O VTuber Recording Tools
</h1>
<p align="center"><b>Version 1.9</b><br><i>A rabbit hole you shouldn't enter, once entered you can't get out.</i></p>
<p align="center">Created by: <b>N4O</b><br/>Last Updated: <b>24/04/2020</b></p>
<p align="center"><a href="https://github.com/noaione/vthell/releases"><strong>Download</strong></a></p>

**Table of Contents**:
- [Information](#information)
- [Requirements](#requirements)
- [Setup](#setup)
    - [Setup python virtualenv](#setup-virtualenv)
    - [Setup rclone](#setup-rclone)
    - [Get "YouTube Data API v3" API key.](#get-youtube-data-api-v3-api-key)
    - **Optional** [Setup Discord Announcer](#setup-discord-announcer-optional)
    - [Setup VTHell](#setup-vthell)
    - [Configuring auto-scheduler](#configuring-auto-scheduler)
    - [Configuring twitcasting](#configuring-twitcasting)
- [Running](#running)
    - [addjob.sh](#addjobsh)
    - [runjob.sh](#runjobsh)
    - [runauto.sh](#runautosh)
    - [runtwit.sh](#runtwitsh)
    - [vtrip.sh](#vtripsh)
    - [vtup.sh](#vtupsh)
- [Troubleshooting](#troubleshooting)
- [Helpful `alias`](#helpful-bashrc-or-alias)

## Information
~~This tools currently doesn't support anyone else beside HoloLive.~~
<br>
~~You are able to use it but it will not work 100% or the upload mapping will be kinda fucked.~~
<br>
~~To be honest, this tools works for every livestream in YouTube. It will only be broken when the stream is recorded and will be uploaded.~~

**This program now support Agency outside Hololive, you can check it on [dataset](https://github.com/noaione/vthell/tree/master/dataset) folder.**

I only fully support Linux for now because Windows is annoying to make this fully automatic and I'm lazy to write up the tutorial.

This tools also utilize [HoloLive Tools](https://hololive.jetri.co/) API and YouTube Data API v3 for YouTube streams.<br>
And utilize twitcasting API for the twitcasting streams.

If you want to see other VLiver to be added to this list, you can contact me at **Discord: N4O#8868**<br>
I'll try to add it to this program.

This tools is not modular yet, but once it setup you can just use it easily.

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
    $ pip3 install -U requests pytz youtube-dl streamlink discord_webhook
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
1. [Download](https://github.com/noaione/vthell/releases) or [clone](https://api.github.com/repos/noaione/vthell/zipball/master) this repository
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

**In `scripts/vthell.py` AND In `scripts/twitcast.py`**<br>
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

[...]

"""
Cookies must be Netscape format or the one that can be opened with CURL.

Netscape format:
URL  INCLUDE_SUBDOMAINS  PATH  HTTPS_ONLY  EXPIRES  COOKIES_NAME  COOKIES_VALUE
.youtube.com  TRUE  /  TRUE  0  SAMPLES  SAMPLEVALUES
"""
COOKIES_NAME = "cookies.txt"  # Your cookies file name
```

**Update 1.9**<br>
This update introduce cookies support to be able to record member-only stream.<br>
Change `COOKIES_NAME` to your cookies that you put on the main vthell folder.

**WARNING**<br>
I only support Netscape format as seen on that top sample.

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
**Main file: [scripts/vtauto_schedule.py](https://github.com/noaione/vthell/blob/master/scripts/vtauto_schedule.py)**

**Update 1.9**
<br>
This update introduce Nijisanji to the auto uploader, you can enable/disable it on the main file.
```py
"""
Set to True or False if you want it to be processed/scheduled automatically

Default:
- Enable Hololive
- Disable Nijisanji
So, it will process Hololive but skip Nijisanji completely.
"""
PROCESS_HOLOLIVE = True
PROCESS_NIJISANJI = False
```

There's 2 main part to edit, `ENABLED_MAP` and `IGNORED_MAP`<br>
`ENABLED_MAP` are streams that will be scheduled if it match one of the defined conditions.<br>
While `IGNORED_MAP` will remove anything that match the conditions.

The default one for `ENABLED_MAP` are:
- Towa ch.
- Korone ch.
- Any title containing: `歌う`
- Any title containing: `歌枠`
- Any title containing: `歌雑談`
- Any title containing: `ASMR`
- Any title containing: `うたうよ`

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

### Configuring Twitcasting
**Main file: [scripts/twitcast.py](https://github.com/noaione/vthell/blob/master/scripts/twitcast.py)**

**NOTE**<br>
I need help expanding the twitcast user ID, please contact me at Discord: N4O#8868

There's only 1 part you need to edit: `ENABLED_USERS` variable<br>

The default one enabled are:
- natsuiromatsuri

You only need to add the user ID to the `ENABLED_USERS` lists<br>
You can check the User ID on `upload_mapping` variable.

## Running
#### [addjob.sh](https://github.com/noaione/vthell/blob/master/addjob.sh)
**./addjob.sh** [youtube_link1] [youtube_link2] [youtube_link_etc]

Supported youtube link format are:
- https://www.youtube.com/watch?v=VIDEOID
- https://youtu.be/VIDEOID

It will create a .json files containing some info that will be parsed by `runjob.sh` or `vthell.py`

Using **Youtube Data API v3** to determine output filename.<br>
**Output filename format**: `[YYYY.MM.DD] TITLE [RESOLUTIONp AAC].mkv`

#### [runjob.sh](https://github.com/noaione/vthell/blob/master/runjob.sh)
**./runjob.sh**

You can use **`cronjob`** to run every minute or whatever interval you want or run it manually.

It will check all `.json` in `jobs` folder and process the one that are not processed yet.

***What will be checked?*** the .json file<br>
The json file contains 3 keys that will be used to check:
- **`startTime`** if the `startTime` not less than 2 minutes left, it will be skipped completely
- **`isDownloaded`** stream `finished`, and file is being muxed and will be uploaded.
- **`isDownloading`** will skip if True to `prevent double recording`.

After **1 minutes left before stream**, it will use **streamlink** to check if stream online or not.<br>
If not continue, if yes start recording.

After stream finished, file will be muxed into .mkv and will be uploaded, .ts file will be deleted and also the .json files.

**Recommended cron schedule:**
```sh
*/1 * * * * /path/to/vthell/runjob.sh
```

#### [runauto.sh](https://github.com/noaione/vthell/blob/master/runauto.sh)
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

#### [runtwit.sh](https://github.com/noaione/vthell/blob/master/runtwit.sh)
**./runtwit.sh**

You can use **`cronjob`** to run every 2 minute or whatever interval you want or run it manually.

It will fetch to Twitcasting frontend API endpoint to check if `ENABLED_USERS` are live or not.<br>
If it's it will add a "LOCK" file to jobs folder to ensure that no duplicate will be added.<br>
After it finish, it will unlock again the file and the final file will be uploaded.<br>

**To customize refer to: [Configuring auto-scheduler](#configuring-twitcasting)**

**Recommended cron schedule:**
```sh
*/2 * * * * /path/to/vthell/runtwit.sh
```

#### [vtrip.sh](https://github.com/noaione/vthell/blob/master/vtrip.sh)
**./vtrip.sh** [url]

Download your vtuber (mainly holo) video from youtube.<br>
Doesn't support playlist.<br>
Output format are: `[YYYY.MM.DD] TITLE [RESOLUTION AAC].mkv`<br>
YYYY.MM.DD are Date uploaded or streamed.<br>
Combine with `vtup.sh` later

[vtrip_helper.py](https://github.com/noaione/vthell/blob/master/scripts/vtrip_helper.py) are helper to determine the output name using Youtube Data API v3.

**Don't use this if you're ripping currently live streamed video, use addjob.sh for that**

#### vtup.sh
**REMOVED**

`vtup.sh` are now removed since version 1.9 since it's support more Agency.


## Troubleshooting
> Stream xxxxxx are paused

Enable it again when the VTuber start streaming by using `./addjob.sh [youtube_link]`

> Error 429

You're being rate limited by YouTube there's nothing you can do except using proxy temporarily

> "Please add VTuber from xxx."

If you want me to add that VTuber into the list, please help me compile them with the same format as most `dataset` list.<br>
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

> Follow logfile
```bash
alias vtl="tail -f -n 80 /path/to/vthell/nvthell.log"
```

> See all the jobs<br>
**WARNING**: You need `jq` in your PATH
```bash
alias vtj='for jobs in /path/to/vthell/jobs/*.json; do jname=`cat $jobs | jq -r '.filename'`; jsurl=`cat $jobs | jq -r '.streamUrl'`; jsdling=`cat $jobs | jq '.isDownloading'`; jsdled=`cat $jobs | jq '.isDownloaded'`; jdtime=`cat $jobs | jq '.startTime'`; jdtime="$(($jdtime + 32400))"; jdtime=`date -d @$jdtime`; printf "Title: ${jname}\nLink: ${jsurl}\nStart Time: ${jdtime/UTC/JST}\Recording? ${jsdling^}   Recorded? ${jsdled^}\n\n"; done'
```