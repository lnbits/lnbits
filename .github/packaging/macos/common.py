"""Sanitized subprocess boundary shared by macOS build and release tools."""

import base64
import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
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


def error_message(error):
    if isinstance(error, ReleaseError):
        return str(error)
    return f"Release operation failed ({type(error).__name__})"


@contextlib.contextmanager
def cleanup_on_exit(action, runner):
    try:
        yield
    except BaseException:
        try:
            action()
        except Exception as error:
            # Keep the original failing operation; report secondary failures too.
            print(
                runner.redact(f"Cleanup also failed: {error_message(error)}"),
                file=sys.stderr,
            )
        raise
    else:
        # Cleanup alone must still fail the release and prevent publication.
        action()


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

    def run(
        self, operation, *args, timeout=300, env=None, check=True, log_output=False
    ):
        print(self.redact(f"macOS: {operation}"), flush=True)
        environment = dict(self.environment, **(env or {}))
        # Sanitize using credentials inherited by this process, even if a caller
        # supplied a different environment for the child.
        try:
            if log_output:
                result = self.run_logged(operation, args, timeout, environment)
            else:
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

    def run_logged(self, operation, args, timeout, environment):
        """Heartbeat long builds; redact complete output without logging arguments."""
        started = time.monotonic()
        command = [str(arg) for arg in args]
        # A private temporary file avoids pipes held open by tool subprocesses.
        with tempfile.TemporaryFile() as log:
            with subprocess.Popen(  # noqa: S603
                command,
                env=clean_environment(environment),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name == "posix",
            ) as process:
                try:
                    while True:
                        remaining = timeout - (time.monotonic() - started)
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(command, timeout)
                        try:
                            process.wait(timeout=min(30, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            elapsed = time.monotonic() - started
                            print(
                                self.redact(
                                    f"macOS: {operation}: running for {elapsed:.0f}s "
                                    f"(limit {timeout}s)"
                                ),
                                flush=True,
                            )
                except BaseException as error:
                    # Stop this tool's process group, never unrelated disk helpers.
                    try:
                        if os.name == "posix":
                            os.killpg(process.pid, signal.SIGKILL)
                        else:
                            process.kill()
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=10)
                    if isinstance(error, subprocess.TimeoutExpired):
                        log.seek(0)
                        error.output = log.read()
                    raise
                log.seek(0)
                output = log.read().decode(errors="replace")
        elapsed = time.monotonic() - started
        print(
            self.redact(
                f"macOS: {operation}: exit {process.returncode} after {elapsed:.1f}s"
            ),
            flush=True,
        )
        if output:
            print(self.redact(output)[-12000:], flush=True)
        return subprocess.CompletedProcess(command, process.returncode, output, "")


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
