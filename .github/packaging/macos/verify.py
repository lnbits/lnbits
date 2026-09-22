"""Verification and smoke checks against the exact final read-only image."""

import os
import plistlib
import sys
import tempfile
from pathlib import Path

from macos.common import ReleaseError, cleanup_on_exit
from macos.signing import native_files, verify_app, verify_code

PACKAGING = Path(__file__).resolve().parents[1]
REQUIRED_DATA = (
    "certifi/cacert.pem",
    "grpc/_cython/_credentials/roots.pem",
    "pyinstrument/renderers/html_resources/app.css",
    "pyinstrument/renderers/html_resources/app.js",
    "random_username/data/adjectives.txt",
    "random_username/data/nouns.txt",
    "lnbits/templates/base.html",
    "lnbits/static/bundle.min.js",
)


def bundled_data(runner, app, arch):
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if (info.get("CFBundleIdentifier"), info.get("LSMinimumSystemVersion")) != (
        "com.lnbits.desktop",
        "15.0",
    ):
        raise ReleaseError("Unexpected bundle identifier or minimum macOS version")
    resources = app / "Contents/Resources"
    for name in REQUIRED_DATA:
        if not (resources / name).is_file():
            raise ReleaseError(f"Missing packaged dependency data: {name}")
    sidecars = app / "Contents/Frameworks/sidecars"
    for name in ("node", "phoenixd", "pins.json", "spark/server.mjs", "supervisor.mjs"):
        if not (sidecars / name).is_file():
            raise ReleaseError(f"Missing bundled funding component: {name}")
    if not (sidecars / "spark/node_modules").is_dir():
        raise ReleaseError("Missing Spark dependencies")
    verify_architecture(runner, app, arch)
    for _, _, files in os.walk(app):
        if any(
            name == ".env.macos-release" or name.endswith((".p12", ".keychain-db"))
            for name in files
        ):
            raise ReleaseError("Signing material must never be bundled")


def verify_architecture(runner, app, arch):
    for path in native_files(app):
        operation = f"Verify native architecture: {path.relative_to(app)}"
        result = runner.run(operation, "/usr/bin/lipo", "-archs", path)
        if arch not in result.stdout.split():
            raise ReleaseError(
                f"Wrong native architecture: {path.relative_to(app)} "
                f"(expected {arch}; found {result.stdout.strip() or 'none'})"
            )
        if path == app / "Contents/MacOS/LNbits" and result.stdout.strip() != arch:
            raise ReleaseError("Launcher must contain exactly the native architecture")


def verify_image(runner, session, output, arch, team=None):
    runner.run(
        "Verify DMG integrity", "/usr/bin/hdiutil", "verify", output, timeout=600
    )
    if team:
        verify_code(runner, output, team, runtime=False)
        runner.run(
            "Validate DMG ticket", "/usr/bin/xcrun", "stapler", "validate", output
        )
        runner.run(
            "Assess DMG Gatekeeper",
            "/usr/sbin/spctl",
            "--assess",
            "--type",
            "open",
            "--context",
            "context:primary-signature",
            "--verbose=2",
            output,
        )
    mount = Path(tempfile.mkdtemp(prefix="lnbits-verify-")).resolve()
    session.state["mount"] = str(mount)
    session.save()
    with cleanup_on_exit(session.detach, runner):
        runner.run(
            "Mount final DMG read-only",
            "/usr/bin/hdiutil",
            "attach",
            output,
            "-mountpoint",
            mount,
            "-nobrowse",
            "-readonly",
            "-plist",
        )
        if not (mount / "Applications").is_symlink() or (
            mount / "Applications"
        ).readlink() != Path("/Applications"):
            raise ReleaseError("DMG is missing its Applications shortcut")
        app = mount / "LNbits.app"
        if team:
            verify_app(runner, app, team, arch)
            runner.run(
                "Assess app Gatekeeper",
                "/usr/sbin/spctl",
                "--assess",
                "--type",
                "execute",
                "--verbose=2",
                app,
            )
            runner.run(
                "Validate app ticket", "/usr/bin/xcrun", "stapler", "validate", app
            )
        else:
            runner.run(
                "Verify development app",
                "/usr/bin/codesign",
                "--verify",
                "--deep",
                "--strict",
                app,
            )
        bundled_data(runner, app, arch)
        python = Path(".venv/bin/python").resolve()
        if not python.is_file():
            python = Path(sys.executable)
        runner.run(
            "Smoke bundled sidecars",
            python,
            PACKAGING / "smoke_sidecars.py",
            app / "Contents/Frameworks/sidecars",
            timeout=180,
        )
        runner.run(
            "Smoke packaged server and shutdown",
            python,
            PACKAGING / "smoke.py",
            app / "Contents/MacOS/LNbits",
            timeout=240,
        )
        runner.run(
            "Smoke packaged launcher and JIT",
            python,
            PACKAGING / "macos/smoke_launcher.py",
            app / "Contents/MacOS/LNbits",
            timeout=240,
        )
