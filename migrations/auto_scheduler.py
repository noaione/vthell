import argparse
from pathlib import Path

import json
import requests

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", help="Port to connect to", type=int, default=12790)
parser.add_argument("-P", "--password", help="Password to connect to the server", required=True)
args = parser.parse_args()

ROOT_DIR = Path(__file__).absolute().parent.parent
DATASET_FOLDER = ROOT_DIR / "dataset"

AUTO_FILE = DATASET_FOLDER / "_auto_scheduler.json"
if not AUTO_FILE.exists():
    print(f"[!] Auto scheduler file not found: {AUTO_FILE}")
    exit(0)


with open(AUTO_FILE, "r") as f:
    auto_scheduler = json.load(f)

print("[*] Testing URL")
try:
    resp = requests.get(f"http://localhost:{args.port}/")
    if resp.status_code != 200:
        print(f"[!] Error connecting to server: {resp.text}")
        exit(1)
except Exception:
    print("[!] Error connecting to server")
    exit(1)

print("[*] Trying to migrate old auto scheduler database...")

headers = {
    "Authorization": f"Password {args.password}",
}

for enabled in auto_scheduler["enabled"]:
    resp = requests.post(
        f"http://localhost:{args.port}/api/auto-scheduler",
        json={"type": enabled["type"], "data": enabled["data"]},
        headers=headers,
    )
    if resp.status_code >= 400:
        print(f"[v][!] Error migrating scheduler {enabled}: {resp.text}")
    else:
        print(f"[v][*] Scheduler {enabled} migrated")

for disabled in auto_scheduler["disabled"]:
    resp = requests.post(
        f"http://localhost:{args.port}/api/auto-scheduler",
        json={"type": disabled["type"], "data": disabled["data"], "include": False},
        headers=headers,
    )
    if resp.status_code >= 400:
        print(f"[x][!] Error migrating scheduler {disabled}: {resp.text}")
    else:
        print(f"[x][*] Scheduler {disabled} migrated")
