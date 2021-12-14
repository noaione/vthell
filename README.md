<h1 align="center">
    <img src="https://media.discordapp.net/attachments/558322816995426305/687238504190574598/CocoOkite.gif"><br>
    N4O VTuber Recording Tools
</h1>
<p align="center"><b>Version 3.0.0</b><br><i>A rabbit hole you shouldn't enter, once entered you can't get out.</i></p>
<p align="center">Created by: <b>N4O</b><br/>Last Updated: <b>XX/XX/20XX</b></p>
<p align="center"><a href="https://github.com/noaione/vthell/releases"><strong>Download</strong></a></p>

**Table of Contents**:
- [Information](#information)
- [Requirements](#requirements)
- [Setup](#setup)
  - [Setup Rclone](#setup-rclone)
  - [Setup YTArchive](#setup-ytarchive)
- [Configuration](#configuration)
- [Running](#running)
  - [Accessing Protected Routes](#accessing-protected-routes)
  - [Auto Scheduler](#auto-scheduler)
- [Improvements](#improvements)
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
RCLONE_DRIVE_TARGET=
MKVMERGE_BINARY=mkvmerge
YTARCHIVE_BINARY=ytarchive
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
- `RCLONE_DRIVE_TARGET` will be your target drive or your remote name that you setup in [Setup Rclone](#setup-rclone)
- `MKVMERGE_BINARY` will be your mkvmerge path
- `YTARCHIVE_BINARY` will be your ytarchve path, you can follow the [Setup YTArchive](#setup-ytarchive) to get your ytarchive up and running.

## Running

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

### Auto Scheduler

The auto scheduler has now been rewritten, if you still have the old one you might want to run the migration scripts.

TBW

## Improvements

Version 3.0 of VTHell is very much different to the original 2.x or 1.x version of it. It includes a full web server to monitor your recording externally, a better task management to allow you to fire multiple download at once, Socket.IO feature to better monitor your data via websocket.

It also now using Holodex API rather than Holotools API since it support many more VTuber.

The other thing is moving from JSON file to SQLite3 database for all the job, this improve performance since we dont need to read/write multiple time to disk.

## License

This project is licensed with MIT License, learn more [here](LICENSE)
