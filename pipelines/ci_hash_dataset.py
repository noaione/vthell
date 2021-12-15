import json
from hashlib import md5
from os.path import splitext
from pathlib import Path
from zipfile import ZipFile

dataset_path = Path(__file__).absolute().parent.parent / "dataset"

all_json_files = list(dataset_path.glob("**/*.json"))
print("[*] Loading datasets")
compiled_dataset = {}
for json_f in all_json_files:
    name, _ = splitext(json_f.name)
    with json_f.open() as f:
        compiled_dataset[name] = json.load(f)

print(f"[*] Datasets loaded ({len(compiled_dataset)} entries)")

print("[*] Hashing dataset...")
as_string = json.dumps(compiled_dataset, sort_keys=True, separators=(",", ":"))
hashed_data = md5(as_string.encode("utf-8")).hexdigest()

print(f"[*] Current hash: {hashed_data}, saving to file...")
with open(dataset_path / "currentversion", "w") as fp:
    fp.write(hashed_data)


zip_archive = dataset_path / "archive.zip"
print(f"[*] Creating archive {zip_archive}")
with ZipFile(str(zip_archive), "w") as zip:
    for json_f in all_json_files:
        zip.write(str(json_f), json_f.name)
print("[*] Done")
