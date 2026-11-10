"""Exercise the shipped executable from a writable directory outside its bundle."""

import os

# ruff: noqa: S101
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

binary = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="lnbits-smoke-") as directory:
    folder = Path(directory)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    environment = dict(
        os.environ,
        DEBUG="false",
        BUNDLE_ASSETS="true",
        PROFILER="true",
        LNBITS_DATA_FOLDER=str(folder / "data"),
        LNBITS_EXTENSIONS_PATH=str(folder),
        LNBITS_EXTENSIONS_DEFAULT_INSTALL="[]",
        LNBITS_BACKEND_WALLET_CLASS="FakeWallet",
        APPIMAGE_EXTRACT_AND_RUN="1",
    )
    stop_file = folder / "stop"
    process = subprocess.Popen(  # noqa: S603
        [
            str(binary),
            "--headless",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--stop-file",
            str(stop_file),
        ],
        cwd=folder,
        env=environment,
    )
    try:
        deadline = time.monotonic() + 120
        for path in ("/", "/static/bundle.min.js", "/?profiler=1"):
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Packaged server exited before it was ready")
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}{path}", timeout=2
                    ) as response:
                        assert response.status == 200
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Packaged server startup timed out"
                        ) from None
                    time.sleep(0.2)
        stop_file.touch()
        assert process.wait(timeout=40) == 0
        with socket.socket() as sock:
            assert (
                sock.connect_ex(("127.0.0.1", port)) != 0
            ), "Server survived launcher shutdown"
    except Exception:
        log = folder / "data" / "logs" / "desktop.log"
        if log.exists():
            print(log.read_text(encoding="utf-8"), file=sys.stderr)
        raise
    finally:
        stop_file.touch()
        if process.poll() is None:
            try:
                process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
