"""Private, recoverable release credentials and temporary keychain lifecycle."""

import json
import os
import re
import shlex
import shutil
import stat
import tempfile
from pathlib import Path

from macos.common import CREDENTIAL_NAMES, ReleaseError, validate_credentials

PROFILE = "lnbits-notarization"


def load_credentials(env_file=None):
    if env_file is None:
        return {name: os.environ.get(name, "") for name in CREDENTIAL_NAMES}
    path = Path(env_file)
    if path.is_symlink() or not path.is_file():
        raise ReleaseError("Expected a regular .env.macos-release file")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ReleaseError("Set .env.macos-release permissions to 0600")
    values = {}
    # Deliberately not shell-sourced and never passed through runtime dotenv.
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not separator or name not in CREDENTIAL_NAMES or name in values:
            raise ReleaseError("Invalid or duplicate key in .env.macos-release")
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]:
                raise ReleaseError("Unclosed quote in .env.macos-release")
            value = value[1:-1]
        values[name] = value
    return values


def select_identity(output, team):
    identities = re.findall(
        r'^\s*\d+\) ([A-Fa-f0-9]{40}) "Developer ID Application: [^"\n]+ '
        r'\(([A-Z0-9]{10})\)"\s*$',
        output,
        re.MULTILINE,
    )
    matches = {
        fingerprint.upper() for fingerprint, owner in identities if owner == team
    }
    if len(matches) != 1:
        raise ReleaseError(
            "Select signing identity: expected exactly one valid Developer ID "
            "Application identity for APPLE_TEAM_ID; check certificate expiry, "
            "private key, team and duplicate certificates"
        )
    return matches.pop()


class Session:
    def __init__(self, path, runner):
        self.path = Path(path).resolve()
        self.runner = runner
        self.state = {
            "directory": None,
            "keychain": None,
            "search_list": None,
            "mount": None,
        }

    def begin(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ReleaseError(
                "A release session already exists; run the documented cleanup command"
            ) from None
        with os.fdopen(descriptor, "w") as stream:
            json.dump(self.state, stream)

    def save(self):
        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            try:
                os.chmod(temporary, 0o600)
                json.dump(self.state, stream)
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def setup(self, credentials):
        certificate = validate_credentials(credentials)
        original = self.runner.run(
            "Read keychain search list",
            "/usr/bin/security",
            "list-keychains",
            "-d",
            "user",
        )
        self.state["search_list"] = shlex.split(original.stdout)
        directory = Path(tempfile.mkdtemp(prefix="lnbits-release-"))
        directory.chmod(0o700)
        keychain = directory / "signing.keychain-db"
        self.state.update(directory=str(directory), keychain=str(keychain))
        self.save()
        p12 = directory / "certificate.p12"
        with p12.open("xb") as stream:
            p12.chmod(0o600)
            stream.write(certificate)
        password = credentials["KEYCHAIN_PASSWORD"]
        self.runner.run(
            "Create temporary keychain",
            "/usr/bin/security",
            "create-keychain",
            "-p",
            password,
            keychain,
        )
        self.runner.run(
            "Unlock temporary keychain",
            "/usr/bin/security",
            "unlock-keychain",
            "-p",
            password,
            keychain,
        )
        self.runner.run(
            "Set keychain timeout",
            "/usr/bin/security",
            "set-keychain-settings",
            "-lut",
            "21600",
            keychain,
        )
        # Keep original entries accessible; every final codesign also uses --keychain.
        self.runner.run(
            "Add temporary keychain",
            "/usr/bin/security",
            "list-keychains",
            "-d",
            "user",
            "-s",
            keychain,
            *self.state["search_list"],
        )
        try:
            self.runner.run(
                "Import Developer ID certificate",
                "/usr/bin/security",
                "import",
                p12,
                "-k",
                keychain,
                "-P",
                credentials["P12_PASSWORD"],
                "-T",
                "/usr/bin/codesign",
                "-T",
                "/usr/bin/security",
            )
        finally:
            p12.unlink(missing_ok=True)
        self.runner.run(
            "Allow unattended codesign",
            "/usr/bin/security",
            "set-key-partition-list",
            "-S",
            "apple-tool:,apple:,codesign:",
            "-s",
            "-k",
            password,
            keychain,
        )
        result = self.runner.run(
            "Select signing identity",
            "/usr/bin/security",
            "find-identity",
            "-v",
            "-p",
            "codesigning",
            keychain,
        )
        identity = select_identity(result.stdout, credentials["APPLE_TEAM_ID"])
        self.runner.run(
            "Store notarization credentials",
            "/usr/bin/xcrun",
            "notarytool",
            "store-credentials",
            PROFILE,
            "--keychain",
            keychain,
            "--apple-id",
            credentials["APPLE_ID"],
            "--team-id",
            credentials["APPLE_TEAM_ID"],
            "--password",
            credentials["APPLE_APP_SPECIFIC_PASSWORD"],
        )
        return identity

    def cleanup(self):
        errors = []
        for action in (self.detach, self.restore_search_list, self.delete_keychain):
            try:
                action()
            except Exception:
                # Continue every cleanup operation; retain state for recovery.
                errors.append(action.__name__)
        if errors:
            raise ReleaseError("Cleanup failed: " + ", ".join(errors))
        if self.state["directory"] and Path(self.state["directory"]).exists():
            shutil.rmtree(self.state["directory"])
        self.path.unlink(missing_ok=True)

    def restore_search_list(self):
        original = self.state["search_list"]
        if original is None:
            return
        self.runner.run(
            "Restore keychain search list",
            "/usr/bin/security",
            "list-keychains",
            "-d",
            "user",
            "-s",
            *original,
        )
        restored = self.runner.run(
            "Verify restored keychain search list",
            "/usr/bin/security",
            "list-keychains",
            "-d",
            "user",
        )
        if shlex.split(restored.stdout) != original:
            raise ReleaseError("Keychain search list restoration did not match")
        self.state["search_list"] = None
        self.save()

    def delete_keychain(self):
        keychain = self.state["keychain"]
        if keychain and Path(keychain).exists():
            self.runner.run(
                "Delete temporary keychain",
                "/usr/bin/security",
                "delete-keychain",
                keychain,
            )
            if Path(keychain).exists():
                raise ReleaseError("Temporary keychain still exists after deletion")
        self.state["keychain"] = None
        self.save()

    def detach(self):
        mount = self.state["mount"]
        if not mount:
            return
        # An attach failure can still leave a mounted device. Query actual state.
        import plistlib

        result = self.runner.run(
            "Inspect mounted images", "/usr/bin/hdiutil", "info", "-plist"
        )
        mounted = any(
            entity.get("mount-point") == mount
            for item in plistlib.loads(result.stdout.encode()).get("images", [])
            for entity in item.get("system-entities", [])
        )
        if mounted:
            self.runner.run("Detach final DMG", "/usr/bin/hdiutil", "detach", mount)
        if Path(mount).exists():
            Path(mount).rmdir()
        self.state["mount"] = None
        self.save()


def cleanup(path, runner):
    session = Session(path, runner)
    if not session.path.exists():
        return
    session.state = json.loads(session.path.read_text())
    session.cleanup()
