"""Own one bundled funding daemon and its persistent wallet, outside LNbits core."""

import base64
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from embit.bip39 import mnemonic_from_bytes, mnemonic_is_valid

PROVIDERS = {"spark": "SparkL2Wallet", "phoenixd": "PhoenixdWallet"}


def bundled_path():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "sidecars"
    return Path(__file__).resolve().parents[2] / "build/sidecars"


def load_profile(folder):
    path = Path(folder).expanduser() / "funding/profile.json"
    if not path.exists():
        return {}
    profile = json.loads(path.read_text())
    if not isinstance(profile, dict) or profile.get("provider") not in PROVIDERS:
        raise ValueError(
            "The funding profile is invalid. Restore your data folder backup."
        )
    return profile


def save_private(path, contents):
    """Replace a complete private file; never leave a partially written seed."""
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.chmod(temporary, 0o600)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def check_port(port):
    with socket.create_server(("127.0.0.1", port)):
        pass


def protect_settings(environment):
    """Keep this launcher's connection settings authoritative over saved settings."""
    from lnbits.settings import readonly_variables, settings

    provider = environment.get("LNBITS_DESKTOP_FUNDING", "none")
    if provider not in PROVIDERS:
        return
    if settings.lnbits_database_url:
        raise ValueError("Use a local SQLite data folder for bundled funding.")
    prefix = "SPARK_L2_" if provider == "spark" else "PHOENIXD_"
    for key, value in environment.items():
        if key.startswith(prefix) or key == "LNBITS_BACKEND_WALLET_CLASS":
            name = key.lower()
            setattr(settings, name, value)
            if name not in readonly_variables:
                readonly_variables.append(name)


class Funding:
    def __init__(self, environment):
        self.environment = environment
        self.provider = environment["LNBITS_DESKTOP_FUNDING"]
        self.port = int(environment["LNBITS_DESKTOP_FUNDING_PORT"])
        self.folder = Path(environment["LNBITS_DATA_FOLDER"]) / "funding"
        self.process = None
        self.log = None
        self.lock = None
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.error = None
        self.stopping_at = None

    def start(self):
        if self.provider == "phoenixd" and sys.platform == "win32":
            raise ValueError("Bundled Phoenixd is available on Linux and macOS.")
        resources = bundled_path()
        node = resources / ("node.exe" if sys.platform == "win32" else "node")
        runtime = resources / (
            "spark/server.mjs" if self.provider == "spark" else "phoenixd"
        )
        if not all(
            path.is_file() for path in (node, resources / "supervisor.mjs", runtime)
        ):
            raise ValueError("Bundled funding sources are missing from this build.")
        if os.environ.get("LNBITS_DATABASE_URL"):
            raise ValueError("Use a local SQLite data folder for bundled funding.")
        check_port(self.port)
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = (self.folder / "owner.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self.lock.seek(0)
                self.lock.write(b"\0")
                self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            profile = load_profile(self.folder.parent)
            if not profile and (self.folder.parent / "database.sqlite3").exists():
                raise ValueError(
                    "Choose a new data folder for bundled funding. Existing balances "
                    "cannot be moved to a new funding wallet."
                )
            if profile and profile.get("provider") != self.provider:
                raise ValueError(
                    "Choose a separate data folder to use a different funding wallet."
                )
            if self.provider == "phoenixd" and not (
                profile.get("phoenix_terms")
                or self.environment.get("LNBITS_DESKTOP_PHOENIX_TERMS") == "true"
            ):
                raise ValueError(
                    "Please acknowledge Phoenixd's backup and liquidity terms."
                )
            self._start(resources, node, profile)
        except BaseException:
            self.close()
            raise

    def _start(self, resources, node, profile):
        data = self.folder / self.provider
        data.mkdir(mode=0o700, exist_ok=True)
        seed_file = data / "seed.dat"
        if seed_file.exists():
            mnemonic = seed_file.read_text().strip()
            if not mnemonic_is_valid(mnemonic):
                raise ValueError(
                    "The saved funding seed is invalid. Restore your backup; "
                    "it will not be replaced."
                )
        elif profile:
            raise ValueError(
                "The funding seed is missing. Restore your backup; "
                "a replacement wallet will not be created."
            )
        else:
            mnemonic = mnemonic_from_bytes(
                secrets.token_bytes(32 if self.provider == "spark" else 16)
            )
            save_private(seed_file, mnemonic + "\n")
        profile.update(provider=self.provider, port=self.port)
        if self.provider == "phoenixd":
            profile["phoenix_terms"] = True
        save_private(self.folder / "profile.json", json.dumps(profile))
        # A new secret per launch also prevents stale saved API keys being reused.
        key = secrets.token_hex(32)
        endpoint = f"http://127.0.0.1:{self.port}"
        self.environment["LNBITS_BACKEND_WALLET_CLASS"] = PROVIDERS[self.provider]
        child_environment = dict(os.environ)
        # Do not inject frozen Python's libraries into the external runtimes.
        for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            child_environment.pop(name, None)
            if original := os.environ.get(name + "_ORIG"):
                child_environment[name] = original
        if sys.platform == "linux":
            child_environment["LD_LIBRARY_PATH"] = os.pathsep.join(
                filter(
                    None,
                    (str(resources / "lib"), child_environment.get("LD_LIBRARY_PATH")),
                )
            )
        if self.provider == "spark":
            self.environment.update(
                SPARK_L2_EXTERNAL_ENDPOINT=endpoint,
                SPARK_L2_EXTERNAL_API_KEY=key,
                SPARK_L2_MNEMONIC=mnemonic,
                SPARK_L2_NETWORK="MAINNET",
            )
            child_environment.update(
                SPARK_SIDECAR_HOST="127.0.0.1",
                SPARK_SIDECAR_PORT=str(self.port),
                SPARK_SIDECAR_API_KEY=key,
                SPARK_MNEMONIC=mnemonic,
                SPARK_NETWORK="MAINNET",
                SPARK_ONCHAIN_ENABLED="false",
                SPARK_SIDECAR_STATE_PATH=str(data / "state.json"),
            )
            request = urllib.request.Request(  # noqa: S310 - fixed loopback URL
                endpoint + "/v1/balance", data=b"", headers={"X-Api-Key": key}
            )
        else:
            config = data / "phoenix.conf"
            lines = config.read_text().splitlines() if config.exists() else []
            lines = [
                line
                for line in lines
                if line.split("=", 1)[0].strip() != "http-password"
            ]
            save_private(config, "\n".join([*lines, f"http-password={key}", ""]))
            self.environment.update(
                PHOENIXD_API_ENDPOINT=endpoint,
                PHOENIXD_API_PASSWORD=key,
                PHOENIXD_DATA_DIR=str(data),
                PHOENIXD_MNEMONIC=mnemonic,
            )
            child_environment.pop("PHOENIX_SEED", None)
            child_environment.update(
                PHOENIX_DATADIR=str(data), LNBITS_DAEMON_PORT=str(self.port)
            )
            token = base64.b64encode(f":{key}".encode()).decode()
            request = urllib.request.Request(  # noqa: S310 - fixed loopback URL
                endpoint + "/getinfo", headers={"Authorization": f"Basic {token}"}
            )
        logs = self.folder.parent / "logs"
        logs.mkdir(exist_ok=True)
        self.log = (logs / f"{self.provider}.log").open("ab")
        self.process = subprocess.Popen(  # noqa: S603
            [str(node), str(resources / "supervisor.mjs"), self.provider],
            env=child_environment,
            cwd=data,
            stdin=subprocess.PIPE,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            start_new_session=sys.platform != "win32",
        )
        threading.Thread(target=self._wait_ready, args=(request,), daemon=True).start()

    def _wait_ready(self, request):
        # Local credentials must never be forwarded through a configured proxy.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args, **_kwargs):
                return None

        client = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        deadline = time.monotonic() + 120
        while not self.stopping.is_set() and self.process.poll() is None:
            try:
                with client.open(request, timeout=2) as response:
                    result = json.load(response)
                if (self.provider == "spark" and "balance_sats" in result) or (
                    self.provider == "phoenixd" and "channels" in result
                ):
                    self.ready.set()
                    return
            except (OSError, ValueError, urllib.error.URLError):
                pass
            if time.monotonic() >= deadline:
                self.error = (
                    "Funding source startup timed out. See its log in the data folder."
                )
                return
            self.stopping.wait(0.25)

    def stop(self):
        if not self.stopping.is_set():
            self.stopping.set()
            self.stopping_at = time.monotonic()
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass  # The daemon may already have exited.

    def poll(self):
        if self.process is None:
            return 0
        if self.stopping_at is not None and time.monotonic() - self.stopping_at > 20:
            if self.process.poll() is None:
                self.process.kill()
        return self.process.poll()

    def close(self):
        self.stop()
        if self.process and self.process.poll() is None:
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.log:
            self.log.close()
        if self.lock:
            self.lock.close()
