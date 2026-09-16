"""Sanitized subprocess boundary shared by macOS build and release tools."""

import base64
import json
import os
import subprocess
import urllib.parse

CREDENTIAL_NAMES = (
    "BUILD_CERTIFICATE_BASE64",
    "P12_PASSWORD",
    "KEYCHAIN_PASSWORD",
    "APPLE_ID",
    "APPLE_TEAM_ID",
    "APPLE_APP_SPECIFIC_PASSWORD",
)


class ReleaseError(Exception):
    """A safe, actionable release failure (never includes a command line)."""


def clean_environment(environment):
    return {
        name: value
        for name, value in environment.items()
        if name not in CREDENTIAL_NAMES
        and name not in ("MACOS_CODESIGN_IDENTITY", "MACOS_ENTITLEMENTS_FILE")
    }


class Runner:
    def __init__(self, credentials=None):
        values = [os.environ.get(name, "") for name in CREDENTIAL_NAMES]
        values += list((credentials or {}).values())
        self.secrets = set()
        for value in filter(None, values):
            self.secrets.update(
                (value, json.dumps(value)[1:-1], urllib.parse.quote(value, safe=""))
            )
        certificate = (credentials or {}).get("BUILD_CERTIFICATE_BASE64", "")
        if certificate:
            self.secrets.add("".join(certificate.split()))
        self.environment = clean_environment(os.environ)
        self.environment["MACOSX_DEPLOYMENT_TARGET"] = "15.0"

    def redact(self, text):
        if isinstance(text, bytes):
            text = text.decode(errors="replace")
        for secret in sorted(self.secrets, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        # No ANSI/control sequences in CI diagnostics.
        return "".join(c for c in text if c in "\n\t" or c.isprintable())

    def run(self, operation, *args, timeout=300, env=None, check=True):
        print(f"macOS: {operation}", flush=True)
        environment = dict(self.environment, **(env or {}))
        # Sanitize using credentials inherited by this process, even if a caller
        # supplied a different environment for the child.
        try:
            result = subprocess.run(  # noqa: S603
                [str(arg) for arg in args],
                env=clean_environment(environment),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            diagnostic = self.redact(exc.stdout or "") + self.redact(exc.stderr or "")
            raise ReleaseError(
                f"{operation}: timed out. {diagnostic[-6000:]}"
            ) from None
        except OSError:
            raise ReleaseError(f"{operation}: could not execute tool") from None
        if check and result.returncode:
            diagnostic = self.redact(result.stdout + result.stderr)
            raise ReleaseError(
                f"{operation}: exit {result.returncode}. {diagnostic[-6000:]}"
            ) from None
        return result


def validate_credentials(values):
    missing = [name for name in CREDENTIAL_NAMES if not values.get(name, "").strip()]
    if missing:
        raise ReleaseError("Missing release credentials: " + ", ".join(missing))
    import re

    if not re.fullmatch(r"[A-Z0-9]{10}", values["APPLE_TEAM_ID"]):
        raise ReleaseError("APPLE_TEAM_ID must be a ten-character Apple team ID")
    try:
        certificate = base64.b64decode(
            "".join(values["BUILD_CERTIFICATE_BASE64"].split()), validate=True
        )
    except ValueError:
        raise ReleaseError("BUILD_CERTIFICATE_BASE64 is not valid base64") from None
    if not certificate:
        raise ReleaseError("BUILD_CERTIFICATE_BASE64 is empty")
    return certificate
