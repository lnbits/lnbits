"""Finalize metadata before signing; image creation never edits the staged app."""

import hashlib
import platform
import plistlib
import shutil
import sys
import tempfile
from pathlib import Path

import tomllib


def output_path():
    from packaging.version import Version

    version = Version(
        tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    )
    return Path("dist", f"LNbits-v{version}-macOS-{platform.machine()}.dmg").resolve()


def finalize_app(app):
    from packaging.version import Version

    version = Version(
        tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    )
    plist = app / "Contents/Info.plist"
    info = plistlib.loads(plist.read_bytes())
    info.update(
        CFBundleIdentifier="com.lnbits.desktop",
        CFBundleDisplayName="LNbits",
        CFBundleShortVersionString=version.base_version,
        CFBundleVersion=version.base_version,
        LSMinimumSystemVersion="15.0",
        LSApplicationCategoryType="public.app-category.finance",
        NSHighResolutionCapable=True,
    )
    plist.write_bytes(plistlib.dumps(info))


def create(app, output, runner, *, signed):
    with tempfile.TemporaryDirectory(prefix="lnbits-dmg-") as directory:
        staging = Path(directory)
        # ditto preserves the stapled ticket, resource forks, xattrs and symlinks.
        runner.run("Copy finalized app", "/usr/bin/ditto", app, staging / "LNbits.app")
        (staging / "Applications").symlink_to("/Applications")
        instructions = "Read me.txt" if signed else "Read me unsigned.txt"
        shutil.copyfile(Path(__file__).with_name(instructions), staging / "Read me.txt")
        runner.run(
            "Create DMG",
            "/usr/bin/hdiutil",
            "create",
            "-volname",
            "LNbits",
            "-srcfolder",
            staging,
            "-fs",
            "HFS+",
            "-format",
            "UDZO",
            "-ov",
            output,
            timeout=600,
        )


def checksum(output):
    digest = hashlib.sha256()
    with output.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"{digest.hexdigest()}  {output.name}\n"


def write_checksum(output):
    path = output.with_suffix(".dmg.sha256")
    path.write_text(checksum(output), encoding="utf-8")
    if path.read_text(encoding="utf-8") != checksum(output):
        path.unlink()
        raise RuntimeError("Final DMG checksum verification failed")


if __name__ == "__main__":
    # Keep the old unsigned command, routed through the single verification path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from macos.release import main

    main(["--unsigned", "--skip-build"])
