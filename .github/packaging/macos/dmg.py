"""Create a versioned, verified DMG from the PyInstaller app on macOS."""

import hashlib
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib
from packaging.version import Version


def run(*args):
    subprocess.run(args, check=True)  # noqa: S603


def main():
    if sys.platform != "darwin":
        raise SystemExit("Build the DMG on macOS.")
    version = Version(
        tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    )
    output = Path("dist", f"LNbits-v{version}-macOS-{platform.machine()}.dmg").resolve()
    identity = os.environ.get("MACOS_CODESIGN_IDENTITY") or "-"
    with tempfile.TemporaryDirectory(prefix="lnbits-dmg-") as directory:
        staging = Path(directory)
        app = staging / "LNbits.app"
        shutil.copytree("dist/LNbits.app", app, symlinks=True)
        plist = app / "Contents/Info.plist"
        with plist.open("rb") as stream:
            info = plistlib.load(stream)
        info.update(
            CFBundleDisplayName="LNbits",
            CFBundleShortVersionString=version.base_version,
            CFBundleVersion=version.base_version,
            LSMinimumSystemVersion="15.0",
            LSApplicationCategoryType="public.app-category.finance",
            NSHighResolutionCapable=True,
        )
        with plist.open("wb") as stream:
            plistlib.dump(info, stream)
        # Updating Info.plist invalidates the outer bundle signature. Nested
        # binaries retain the signatures applied by PyInstaller during the build.
        signing = ["/usr/bin/codesign", "--force", "--sign", identity]
        if identity != "-":
            signing += ["--options", "runtime", "--timestamp"]
        if entitlements := os.environ.get("MACOS_ENTITLEMENTS_FILE"):
            signing += ["--entitlements", entitlements]
        run(*signing, str(app))
        run("/usr/bin/codesign", "--verify", "--deep", "--strict", str(app))
        (staging / "Applications").symlink_to("/Applications")
        shutil.copyfile(
            Path(__file__).with_name("Read me.txt"), staging / "Read me.txt"
        )
        run(
            "/usr/bin/hdiutil",
            "create",
            "-volname",
            "LNbits",
            "-srcfolder",
            str(staging),
            "-fs",
            "HFS+",
            "-format",
            "UDZO",
            "-ov",
            str(output),
        )
    run("/usr/bin/hdiutil", "verify", str(output))
    digest = hashlib.sha256()
    with output.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    output.with_suffix(".dmg.sha256").write_text(
        f"{digest.hexdigest()}  {output.name}\n", encoding="utf-8"
    )
    print(output)


if __name__ == "__main__":
    main()
