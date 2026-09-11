"""Build the same desktop entry point on the target operating system."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import wasmtime
from prepare_sidecars import main as prepare_sidecars
from PyInstaller.depend.bindepend import get_imports

os.environ["DEBUG"] = "false"
prepare_sidecars()

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
    "--onedir" if sys.platform == "darwin" else "--onefile",
    "--name",
    "LNbits" if sys.platform == "darwin" else "lnbits",
    "--specpath",
    "build",
    "--hidden-import=embit",
    "--hidden-import=bitstring.bitstore_bitarray",
    "--collect-data=pyinstrument",
    "--collect-data=random_username",
]
# Keep external executables as binaries so macOS signs them with the app.
sidecars = Path("build/sidecars").resolve()
for resource in sidecars.iterdir():
    kind = (
        "--add-binary"
        if resource.name in ("node", "node.exe", "phoenixd")
        else "--add-data"
    )
    destination = "sidecars/spark" if resource.is_dir() else "sidecars"
    args += [kind, f"{resource}:{destination}"]
    if sys.platform == "linux" and resource.name in ("node", "phoenixd"):
        # Phoenixd still needs libcrypt.so.1; newer distros need it bundled.
        for name, path in get_imports(str(resource)):
            if name in (
                "libcrypt.so.1",
                "libz.so.1",
                "libgcc_s.so.1",
                "libstdc++.so.6",
            ):
                if path is None:
                    raise RuntimeError(
                        f"Install {name} before building bundled funding"
                    )
                args += ["--add-binary", f"{path}:sidecars/lib"]
# Wasmtime opens its native library by package-relative path via ctypes.
for library in Path(wasmtime.__file__).parent.glob("*/*"):
    if library.suffix in (".so", ".dll", ".dylib"):
        args += ["--add-binary", f"{library}:wasmtime/{library.parent.name}"]
if sys.platform == "win32":
    icon = Path(__file__).resolve().parent / "linux/AppDir/lnbits.png"
    args += [
        "--hide-console",
        "hide-early",
        f"--icon={icon}",
    ]
if sys.platform == "darwin":
    args += [
        "--windowed",
        "--osx-bundle-identifier=com.lnbits.desktop",
        f"--icon={Path(__file__).resolve().parent / 'linux/AppDir/lnbits.png'}",
    ]
    if identity := os.environ.get("MACOS_CODESIGN_IDENTITY"):
        args += ["--codesign-identity", identity]
    if entitlements := os.environ.get("MACOS_ENTITLEMENTS_FILE"):
        args += ["--osx-entitlements-file", entitlements]
for package in packages:
    args += ["--collect-all", package]
for package in ("breez_sdk", "breez_sdk_liquid"):
    if importlib.util.find_spec(package):
        args += ["--collect-all", package, "--collect-binaries", package]
args.append(".github/packaging/desktop.py")
subprocess.run(args, check=True)  # noqa: S603
