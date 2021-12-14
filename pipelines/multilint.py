"""
MIT License

Copyright (c) 2020-present noaione

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import os
import subprocess as sp
from pathlib import Path

args = argparse.ArgumentParser()
args.add_argument("--skip-install", action="store_true", help="Skip installing dependencies")
args.add_argument("--skip-venv-enter", action="store_true", help="Skip Entering virtualenv")
parser = args.parse_args()

current_path = Path(__file__).absolute().parent.parent
print(f"[*] Running at {current_path}")

# Check venv paths
valid_venv_paths = [current_path / "venv", current_path / "env", current_path / ".venv"]

valid_venv: Path = None
for path in valid_venv_paths:
    if path.exists():
        valid_venv = path
        break


if valid_venv is None:
    # Create venv
    print("[?] Creating venv since it's missing!")
    venv_exec = sp.Popen(["pip", "install", "virtualenv"], stdout=sp.DEVNULL, stderr=sp.DEVNULL).wait()
    venv_path = sp.Popen(["virtualenv", "venv"], stdout=sp.DEVNULL, stderr=sp.DEVNULL).wait()
    if venv_path != 0:
        raise Exception("Failed to create venv")
    valid_venv = current_path / "venv"
print(f"[*] Using venv at {valid_venv}")


# Activate venv
if not parser.skip_venv_enter:
    if os.name == "nt":
        activate_script = valid_venv / "Scripts" / "activate.bat"
        sp.run(["cmd", "/C", str(activate_script)])
    else:
        activate_script = valid_venv / "bin" / "activate"
        sp.run(["source", str(activate_script)])

# Install requirements
requirements_path = current_path / "requirements-dev.txt"
constraints_path = current_path / "constraints.txt"
if not parser.skip_install:
    print(f"[*] Installing requirements from {requirements_path}")
    sp.run(
        [
            "pip",
            "install",
            "-r",
            str(requirements_path),
            "-c",
            str(constraints_path),
        ],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )


print("[*] Running tests")
print("[*] Running safety test...")
safety_res = sp.Popen(["safety", "check", "--full-report"]).wait()
print("[*] Running isort test...")
isort_res = sp.Popen(["isort", "-c", "internals"]).wait()
print("[*] Running flake8 test...")
flake8_res = sp.Popen(
    ["flake8", "--statistics", "--show-source", "--benchmark", "--tee", "internals", "app.py", "asgi.py"]
).wait()

results = [(safety_res, "safety"), (isort_res, "isort"), (flake8_res, "flake8")]
any_error = False

for res in results:
    if res[0] != 0:
        print(f"[-] {res[1]} returned an non-zero code")
        any_error = True
    else:
        print(f"[+] {res[1]} passed")

if any_error:
    print("[-] Test finished, but some tests failed")
    exit(1)
print("[+] All tests passed")
exit(0)
