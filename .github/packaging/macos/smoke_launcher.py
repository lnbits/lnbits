"""Exercise the mounted launcher with external disposable data and no wallet."""

import os
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def stop_launcher(process):
    if process.poll() is not None:
        return
    # The launcher and its multiprocessing worker own this process group.
    # Give Tk/server shutdown a chance before escalating after a timeout.
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=40)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def main(binary):
    with tempfile.TemporaryDirectory(prefix="lnbits-launcher-smoke-") as directory:
        with socket.create_server(("127.0.0.1", 0)) as sock:
            port = sock.getsockname()[1]
        environment = dict(
            os.environ,
            HOST="127.0.0.1",
            PORT=str(port),
            DEBUG="false",
            LNBITS_DATA_FOLDER=directory,
            LNBITS_EXTENSIONS_PATH=directory,
            LNBITS_BACKEND_WALLET_CLASS="FakeWallet",
            LNBITS_EXTENSIONS_DEFAULT_INSTALL="[]",
        )
        process = subprocess.Popen(  # noqa: S603
            [binary, "--smoke-test-gui"],
            env=environment,
            cwd=directory,
            start_new_session=True,
        )
        try:
            if process.wait(timeout=180):
                raise RuntimeError("Packaged GUI smoke process failed")
        finally:
            stop_launcher(process)
        if not (Path(directory) / "database.sqlite3").is_file():
            raise RuntimeError("Packaged GUI did not start LNbits")
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError("Server survived packaged launcher shutdown")


if __name__ == "__main__":
    main(str(Path(sys.argv[1]).resolve()))
