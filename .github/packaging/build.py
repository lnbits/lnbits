"""Build the same desktop entry point on the target operating system."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import wasmtime

os.environ["DEBUG"] = "false"

packages = [
    "embit",
    "bitstring",
    "bitarray",
    "coincurve",
    "wasmtime",
    "lnbits",
    "sqlalchemy",
    "aiosqlite",
]
args = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--clean",
    "--noconfirm",
    "--onefile",
    "--name",
    "lnbits",
    "--specpath",
    "build",
    "--hidden-import=embit",
    "--hidden-import=bitstring.bitstore_bitarray",
    "--collect-data=pyinstrument",
    "--collect-data=random_username",
]
# Wasmtime opens its native library by package-relative path via ctypes.
for library in Path(wasmtime.__file__).parent.glob("*/*"):
    if library.suffix in (".so", ".dll", ".dylib"):
        args += ["--add-binary", f"{library}:wasmtime/{library.parent.name}"]
if sys.platform == "win32":
    args += [
        "--hide-console",
        "hide-early",
        "--icon=.github/packaging/linux/AppDir/lnbits.png",
    ]
for package in packages:
    args += ["--collect-all", package]
for package in ("breez_sdk", "breez_sdk_liquid"):
    if importlib.util.find_spec(package):
        args += ["--collect-all", package, "--collect-binaries", package]
args.append(".github/packaging/desktop.py")
subprocess.run(args, check=True)  # noqa: S603
