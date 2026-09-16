"""Sign and verify actual bundled code, including native files collected as data."""

import json
import os
import plistlib
import re
from pathlib import Path

from macos.common import ReleaseError
from macos.credentials import PROFILE

MACH_MAGICS = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}
ENTITLEMENTS = Path(__file__).with_name("entitlements")


def native_files(app):
    files = []
    for directory, _, names in os.walk(app, followlinks=False):
        for name in names:
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                continue
            with path.open("rb") as stream:
                if stream.read(4) in MACH_MAGICS:
                    files.append(path)
    if not files:
        raise ReleaseError("No Mach-O code found in application")
    return sorted(files, key=lambda p: (-len(p.parts), str(p)))


def code_targets(app):
    files = native_files(app)
    bundles = set()
    for path in files:
        for parent in path.parents:
            if parent == app:
                break
            if parent.suffix in (".framework", ".app", ".xpc", ".bundle"):
                bundles.add(parent)
    return [*sorted([*files, *bundles], key=lambda p: (-len(p.parts), str(p))), app]


def entitlement_file(path, app, arch):
    if path == app or path == app / "Contents/MacOS/LNbits":
        default = ENTITLEMENTS / "python.plist"
        configured = os.environ.get("MACOS_ENTITLEMENTS_FILE")
        if configured:
            candidate = Path(configured).resolve()
            if plistlib.loads(candidate.read_bytes()) != plistlib.loads(
                default.read_bytes()
            ):
                raise ReleaseError(
                    "MACOS_ENTITLEMENTS_FILE must match the documented Python policy"
                )
            return candidate
        return default
    if path.name == "node":
        return ENTITLEMENTS / "node.plist"
    return None


def requirement(team, *, app=False):
    result = (
        "anchor apple generic and certificate leaf[field.1.2.840.113635.100.6.1.13] "
        f'exists and certificate leaf[subject.OU] = "{team}"'
    )
    if app:
        result += ' and identifier "com.lnbits.desktop"'
    return result


def sign(runner, path, identity, keychain=None, entitlements=None, *, runtime=True):
    args = ["/usr/bin/codesign", "--force", "--sign", identity]
    if identity != "-":
        args += ["--keychain", str(keychain), "--timestamp"]
        if runtime:
            args += ["--options", "runtime"]
    if entitlements:
        args += ["--entitlements", str(entitlements)]
    runner.run("Sign code" if runtime else "Sign DMG", *args, path)


def verify_code(runner, path, team, *, app=False, runtime=True, entitlements=None):
    args = ["/usr/bin/codesign", "--verify", "--strict", "--all-architectures"]
    if app:
        args += ["--deep"]
    # Without the leading '=', codesign treats the requirement as a file path.
    args += ["-R", "=" + requirement(team, app=app), path]
    runner.run("Verify Developer ID signature", *args)
    details = runner.run(
        "Inspect signature", "/usr/bin/codesign", "--display", "--verbose=4", path
    )
    details = details.stdout + details.stderr
    if f"TeamIdentifier={team}\n" not in details or not re.search(
        r"^Timestamp=.+", details, re.M
    ):
        raise ReleaseError("Signature is missing the expected team or secure timestamp")
    if runtime and not re.search(r"flags=.*\bruntime\b", details):
        raise ReleaseError("Signature is missing hardened runtime")
    if runtime:
        result = runner.run(
            "Inspect entitlements",
            "/usr/bin/codesign",
            "--display",
            "--entitlements",
            ":-",
            path,
        )
        actual = plistlib.loads(result.stdout.encode()) if result.stdout.strip() else {}
        expected = plistlib.loads(entitlements.read_bytes()) if entitlements else {}
        if actual != expected:
            raise ReleaseError(
                "Signed entitlements differ from the minimal runtime policy"
            )


def sign_app(runner, app, identity, keychain, arch):
    for path in code_targets(app):
        sign(runner, path, identity, keychain, entitlement_file(path, app, arch))


def verify_app(runner, app, team, arch):
    for path in code_targets(app):
        verify_code(
            runner,
            path,
            team,
            app=path == app,
            entitlements=entitlement_file(path, app, arch),
        )


def notarize(runner, artifact, keychain):
    authentication = ["--keychain", keychain, "--keychain-profile", PROFILE]
    # Separate submit and wait retain the ID even when waiting times out. There
    # is one submission for the app ZIP and one for the final signed DMG.
    result = runner.run(
        "Submit notarization",
        "/usr/bin/xcrun",
        "notarytool",
        "submit",
        artifact,
        *authentication,
        "--output-format",
        "json",
        timeout=900,
    )
    try:
        submission = json.loads(result.stdout)["id"]
        if not re.fullmatch(r"[a-fA-F0-9-]{36}", submission):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ReleaseError(
            "Notarization submission did not return a valid JSON ID"
        ) from None
    print(f"Notarization submission: {submission}", flush=True)
    result = runner.run(
        f"Wait for notarization {submission}",
        "/usr/bin/xcrun",
        "notarytool",
        "wait",
        submission,
        *authentication,
        "--timeout",
        "30m",
        "--output-format",
        "json",
        timeout=1860,
        check=False,
    )
    try:
        status = json.loads(result.stdout)["status"]
    except (ValueError, KeyError, TypeError):
        status = "Unknown"
    print(runner.redact(f"Notarization {submission}: {status}"), flush=True)
    if result.returncode or status != "Accepted":
        log = runner.run(
            f"Fetch notarization log {submission}",
            "/usr/bin/xcrun",
            "notarytool",
            "log",
            submission,
            *authentication,
            timeout=120,
            check=False,
        )
        diagnostic = runner.redact(
            result.stdout + result.stderr + log.stdout + log.stderr
        )
        raise ReleaseError(
            f"Notarization {submission} was not Accepted. {diagnostic[-12000:]}"
        )


def staple(runner, artifact):
    runner.run("Staple ticket", "/usr/bin/xcrun", "stapler", "staple", artifact)
    runner.run(
        "Validate stapled ticket", "/usr/bin/xcrun", "stapler", "validate", artifact
    )
