<h1 align="center">
    <img src="https://media.discordapp.net/attachments/558322816995426305/687238504190574598/CocoOkite.gif"><br>
    N4O VTuber Recording Tools
</h1>
<p align="center"><b>Version 3.0.0</b><br><i>A rabbit hole you shouldn't enter, once entered you can't get out.</i></p>
<p align="center">Created by: <b>N4O</b><br/>Last Updated: <b>16/12/2021</b></p>
<p align="center"><a href="https://github.com/noaione/vthell/releases"><strong>Download</strong></a></p>

**Table of Contents**:
- [Information](#information)
- [Requirements](#requirements)
- [Setup](#setup)
  - [Setup Rclone](#setup-rclone)
  - [Setup YTArchive](#setup-ytarchive)
- [Configuration](#configuration)
- [Running and Routes](#running-and-routes)
  - [Routes](#routes)
  - [Auto Scheduler](#auto-scheduler)
    - [Migration](#migration)
  - [Accessing Protected Routes](#accessing-protected-routes)
  - [Socket.IO](#socketio)
- [Improvements](#improvements)
- [Dataset](#dataset)
- [License](#license)

## Information

The v3 version of VTHell is a big rewrite from previous version, while previous version use multiple scripts now this version includes a single webserver with other stuff that will automatically download/upload/archive your stuff.

This program utilize the [Holodex](https://holodex.net) API to fetch Youtube stream and information about it.

The program also use a specific dataset to map upload path, if its need to be improved feel free to open a new pull request.

## Requirements
- Python 3.7+
- mkvmerge (mkvtoolnix)
- rclone
- ytarchive

## Setup

This project utilize [Poetry](https://python-poetry.org/) to manage its project, please follow [this](https://github.com/python-poetry/poetry#installation) instruction to install [Poetry](https://python-poetry.org/).

After you have installed poetry run all of this command:
1. `poetry install`
2. `cp .env.example .env`

This will install all the requirements and copy the example environment into a proper env file.

### Setup Rclone
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

### Setup YTArchive

[YTArchive](https://github.com/Kethsar/ytarchive) is a tool to download a youtube stream from the very beginning of the stream. This tools works much better rather than Streamlink for now.

1. Download the latest version of ytarchive: https://github.com/Kethsar/ytarchive/releases/latest
2. Select the correct distribution
3. Extract the file
4. Create a new folder called `bin` in the root folder of vthell
5. Copy the extracted file into there, it should now look like this:

```bash
[agrius ~/vthell/bin] ls -alh
total 7.3M
drwx------  2 mizore mizore 4.0K Dec 14 21:57 .
drwxr-xr-x 11 mizore mizore 4.0K Dec 14 21:57 ..
-rwxr-xr-x  1 mizore mizore 7.3M Oct 20 23:58 ytarchive
```

## Configuration

VTHell v3 have this following configuration needed:

```yml
# -- Web Server Config --
# THe port to run the web server on
PORT=12790
# Enable if you're planning to use Reverse Proxy like Nginx
WEBSERVER_REVERSE_PROXY=false
# Set the secret key here if you want to use reverse proxy
WEBSERVER_REVERSE_PROXY_SECRET=this-is-a-very-secure-reverse-proxy-secret
# Set the web password, will be use for authentication
WEBSERVER_PASSWORD=this-is-a-very-secure-web-password

# -- VTHell Config --
# Database name
VTHELL_DB=vth.db
# The waiting time for each download check in seconds
VTHELL_LOOP_DOWNLOADER=60
# The waiting time for each auto scheduler check in seconds
VTHELL_LOOP_SCHEDULER=180
# The grace period for the downloader before starting the download
# waiting process in seconds
VTHELL_GRACE_PERIOD=120

# Your Holodex API Key, you can get it from your profile section
HOLODEX_API_KEY=

# Binary path location and more
RCLONE_BINARY=rclone
RCLONE_DISABLE=0
RCLONE_DRIVE_TARGET=
MKVMERGE_BINARY=mkvmerge
YTARCHIVE_BINARY=ytarchive

# Notification helper
NOTIFICATION_DISCORD_WEBHOOK=
```

- `PORT` just means what port it will run on (if you run the app file directly)
- `WEBSERVER_REVERSE_PROXY` enable if you need reverse proxy feature
- `WEBSERVER_REVERSE_PROXY_SECRET` this need to be set if you enable reverse proxy, learn more [here](https://sanicframework.org/en/guide/deployment/nginx.html#proxied-sanic-app).
  You can generate a random one with: `openssl rand -hex 32`
- `WEBSERVER_PASSWORD` this will be your password to access protected resources.

- `VTHELL_DB` is your database filename
- `VTHELL_LOOP_DOWNLOADER` will be your downloader timer, which means the scheduler will run every x seconds that are specified (default 60 seconds)
- `VTHELL_LOOP_SCHEDULER` will be your auto scheduler timer, which means the scheduler will run every x seconds that are specified (default 180 seconds).
  This one will run the auto scheduler that will fetch and automatically add the new job to the database
- `VTHELL_GRACE_PERIOD` how long should the program waits before start trying to download the stream (in seconds, default 2 minutes)
- `HOLODEX_API_KEY` will be your Holodex API key which you can get from your profile page
- `RCLONE_BINARY` will be the full path to your rclone (or you can add it to your system PATH)
- `RCLONE_DISABLE` if you set it to `1`, it will disable rclone/upload step and will save the data to your local disk at `streamdump/`
- `RCLONE_DRIVE_TARGET` will be your target drive or your remote name that you setup in [Setup Rclone](#setup-rclone)
- `MKVMERGE_BINARY` will be your mkvmerge path
- `YTARCHIVE_BINARY` will be your ytarchve path, you can follow the [Setup YTArchive](#setup-ytarchive) to get your ytarchive up and running.
- `NOTIFICATION_DISCORD_WEBHOOK` will be used to announce any update to your scheduling. Must be a valid Discord Webhook link.

## Running and Routes

After you configure it properly, you can start running with Uvicorn or invoking the app.py file directly.

**Via Uvicorn**

```py
poetry run uvicorn asgi:app
```

You can see more information [here](https://www.uvicorn.org/deployment/)

**Invoking directly**

1. Make sure you're in the virtualenv
2. Modify the port you want in the `.env` file
3. Run with `python3 app.py` to start the webserver

### Routes

> **POST `/api/schedule`**, schedule a single video.

**Returns 200** with the added video on success.<br>
**Authentication needed**<br>
**On fail** it will return a JSON with `error` field.

This route allows you to schedule a video manually. If video already scheduled, it will replace some stuff but not everything.

This route accept JSON data with this format:

```json
{
  "id": "abcdef12345"
}
```

`id` is the youtube video ID that will be fetched to Holodex API to check if it's still live/upcoming.

> **DELETE `/api/schedule`**, delete single scheduled video.

**Returns 200** with deleted video on success.<br>
**Authentication needed**<br>
**On fail** it will return a JSON with `error` field.

This route will delete a specific video and return the deleted video if found, the data is the following:

```json
{
  "id": "bFNvQFyTBx0",
  "title": "【ウマ娘】本気の謝罪ガチャをさせてください…【潤羽るしあ/ホロライブ】",
  "start_time": 1639559148,
  "channel_id": "UCl_gCybOJRIgOXw6Qb4qJzQ",
  "is_member": false,
  "status": "DOWNLOADING",
  "error": null
}
```

The deletion only work if the status is either:
- `WAITING`
- `DONE`
- `CLEANUP`

If it's anything else, it will return **406 Not Acceptable** status code.

> **GET `/api/status`**, get the status of all scheduled video.

**Returns 200** with a list scheduled video on success.

This routes accept the following query parameters:
- `include_done`, adding this and setting it into `1` or `true` will include all scheduled video including the one that are already finished.

```json
[
  {
    "id": "bFNvQFyTBx0",
    "title": "【ウマ娘】本気の謝罪ガチャをさせてください…【潤羽るしあ/ホロライブ】",
    "start_time": 1639559148,
    "channel_id": "UCl_gCybOJRIgOXw6Qb4qJzQ",
    "is_member": false,
    "status": "DOWNLOADING",
    "error": null
  }
]
```

All the data is self-explanatory, the `status` is one of this enum:
- `WAITING` means that it's not yet started
- `PREPARING` means the recording process is started and now waiting for stream to start
- `DOWNLOADING` means that the stream is being recorded
- `MUXING` means that the stream has finished downloading and now being muxed into `.mkv` format
- `UPLOAD` means that the stream is now being uploaded to the specified folder
- `CLEANING` means that upload process is done and now the program is cleaning up downloaded files.
- `DONE` means that the job is finished
- `ERROR` means an error occured, see the `error` field to learn more.

> **GET `/api/status/:id`**, get the status of a single job

**Returns 200** with a requested video on success.<br>
**On fail** it will return a JSON with `error` key.

It does the same thing as above route, but only for a single job and returns a dictionary instead of list.

### Auto Scheduler

The auto scheduler is a feature where the program will check every X seconds to the Holodex API for ongoing/upcoming live stream and will schedule anything that match the criteria.

**Routes**

The following are the routes available to add/remove/modify scheduler:

> **GET `/api/auto-scheduler`**, fetch all the auto scheduler.

**Returns 200** on success with the following data:

```json
{
  "include": [
    {
      "id": 1,
      "type": "channel",
      "data": "UC1uv2Oq6kNxgATlCiez59hw",
      "chains": null
    },
    {
      "id": 2,
      "type": "word",
      "data": "ASMR",
      "chains": [
        {
          "type": "group",
          "data": "hololive"
        }
      ]
    }
  ],
  "exclude": [
    {
      "id": 3,
      "type": "word",
      "data": "(cover)",
      "chains": null
    },
  ]
}
```

The data format as seen above includes:
- `type`, which is the type of the data. It must be the following enum:
  - `word`: to check if specific word exist in the title. (case-insensitive)
  - `regex_word`: same as above, but it use regex. (case-insensitive)
  - `group`: check if it match the organization or group (case-insensitive)
  - `channel`: check if channel ID match (case-sensitive)
- `data`: a string following the format of specified `type`
- `chains`: A list of data to be chained with the original data check. If chains are defined, all of them must be matching to be scheduled.
  - This only works on the following type: `word`, `regex_word`
  - This only works on `include` filters only right now.

You can add new scheduler by sending a POST request to this following route:

> **POST `/api/auto-scheduler`**, add new scheduler filter

**Returns 201** on success<br />
**Authentication needed**<br />
**On fail** it will return a JSON with `error` field.

This route accepts a JSON data with this format:

```json
{
  "type": "string-or-type-enum",
  "data": "string",
  "chains": null,
  "include": true
}
```

`type` must be the enum specified above, `data` must be a string, and `include` means if it should be included or excluded when processing the filters later.

Chains can be either, a dictionary/map for single chain, or a list for multiple chains. It can also be none if you dont need it.

Chains will be ignored automatically if `type` is not `word` or `regex_word`.

> **PATCH `/api/auto-scheduler/:id`**, modify specific scheduler filter.

**Returns 204** on success<br />
**Authentication needed**<br />
**On fail** it will return a JSON with `error` field.

This route accepts all of this JSON data:

```json
{
  "type": "string-or-type-enum",
  "data": "string",
  "chains": null,
  "include": true
}
```

All of it are optional, but you must specify something if you want to modify it.

`:id` can be found from using the `GET /api/auto-scheduler`.

> **DELETE `/api/auto-scheduler/:id`**, delete specific scheduler filter.

**Returns 200** on success with the deleted data<br />
**Authentication needed**<br />
**On fail** it will return a JSON with `error` field.

`:id` can be found from using the `GET /api/auto-scheduler`.

#### Migration

The auto scheduler has now been rewritten, if you still have the old one you might want to run the migration scripts.

```py
$ python3 migrations/auto_scheduler.py
```

Make sure you have the `_auto_scheduler.json` in the `dataset` folder, and make sure the webserver is running.

### Accessing Protected Routes

Some routes are protected with password to make sure not everyone can use it. To access it, you need to set the `WEBSERVER_PASSWORD` and copy te value elsewhere.

After that to access it, you need to set either of following header:
- `Authorization`: You also need to prefix it with `Password ` (ex: `Password 123`)
- `X-Auth-Token`: *No extra prefix*
- `X-Password`: *No extra prefix*

The program will first check it in `Authorization` header then the both `X-*` header.

**Sample request**

```sh
curl -X POST -H "Authorization: Password SecretPassword123" http://localhost:12790/api/add
```

```sh
curl -X POST -H "X-Password: SecretPassword123" http://localhost:12790/api/add
```

```sh
curl -X POST -H "X-Auth-Token: SecretPassword123" http://localhost:12790/api/add
```

### Socket.IO

**You need Socket.IO 4.x for JS Client**

This program also support watching the data over Socket.IO client. You can connect to the `/vthell` namespace to listen to all the emitter.

Here are the event:
> `job_update`

Will be emitted everytime there is an update on the job status. It will broadcast the following data:

```json
{
  "id": "123",
  "title": "optional",
  "start_time": "optional",
  "channel_id": "optional",
  "is_member": "optional",
  "status": "DOWNLOADING",
  "error": "An error if possible"
}
```

or

```
{
  "id": "123",
  "status": "DOWNLOADING",
  "error": "An error if possible"
}
```

The `error` field might be not available if the `status` is not `ERROR`.

The only data that will always be sent is `id` and `status`, if you got the extra field like `title`. It means someone called the `/api/schedule` API and the existing job data got replaced with some new data. Please maks sure you handle it properly! 

> `job_scheduled`

This will be emitted everytime autoscheduler added a new scheduled job automatically. It will contains the following data as an example:

```json
{
  "id": "bFNvQFyTBx0",
  "title": "【ウマ娘】本気の謝罪ガチャをさせてください…【潤羽るしあ/ホロライブ】",
  "start_time": 1639559148,
  "channel_id": "UCl_gCybOJRIgOXw6Qb4qJzQ",
  "is_member": false,
  "status": "DOWNLOADING"
}
```

> `job_deleted`

This will be emitted whenever a job was deleted from the database. It will contains the follwing data:

```json
{
  "id": "bFNvQFyTBx0"
}
```

> `connect_job_init`

This will be called as soon as you established connection with the Socket.IO server. It will be used so you can store the current state without needing to use the API.

The data will be the same as requesting to the `/api/status` (without the job with `DONE` status)

## Improvements

Version 3.0 of VTHell is very much different to the original 2.x or 1.x version of it. It includes a full web server to monitor your recording externally, a better task management to allow you to fire multiple download at once, Socket.IO feature to better monitor your data via websocket.

It also now using Holodex API rather than Holotools API since it support many more VTuber.

The other thing is moving from JSON file to SQLite3 database for all the job, this improve performance since we dont need to read/write multiple time to disk.

Oh, and I guess now it support Windows since it does not rely on some linux only feature.

## Dataset

With v3, the dataset is now on its own repository, you can access it here: https://github.com/noaione/vthell-dataset

The dataset repo will be fetched every 1 hour to see if the deployed hash changes.

If you have suggestion for new dataset, removal, and more. Please visit the repo and open a PR or Issue there!

## License

This project is licensed with MIT License, learn more [here](LICENSE)
