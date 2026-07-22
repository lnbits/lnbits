from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.error import URLError

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from tests.e2e.helpers import LNbitsE2EServer, request_json


@pytest.fixture(scope="session")
def lnbits_e2e_server(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[LNbitsE2EServer]:
    data_dir = tmp_path_factory.mktemp("lnbits-e2e")
    log_file = data_dir / "server.log"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    username = "superadmin"
    password = "secret1234"

    env = {
        **os.environ,
        "AUTH_HTTPS_ONLY": "false",
        "DEBUG": "true",
        "HOST": "127.0.0.1",
        "LNBITS_ADMIN_UI": "true",
        "LNBITS_BACKEND_WALLET_CLASS": "FakeWallet",
        "LNBITS_DATA_FOLDER": str(data_dir),
        "LNBITS_ENABLE_LOG_TO_FILE": "false",
        "LNBITS_EXTENSIONS_MANIFESTS": "[]",
        "LNBITS_EXTENSIONS_PATH": str(data_dir),
        "PORT": str(port),
        "PYTHONUNBUFFERED": "1",
    }

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "lnbits.__main__:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]

    with log_file.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    try:
        _complete_first_install(base_url, username, password, log_file, process)
        yield LNbitsE2EServer(
            base_url=base_url,
            username=username,
            password=password,
        )
    finally:
        _terminate_process_group(process)


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(browser: Browser, lnbits_e2e_server: LNbitsE2EServer) -> Iterator[Page]:
    context = browser.new_context(
        base_url=lnbits_e2e_server.base_url,
        viewport={"width": 1280, "height": 900},
    )
    context.add_init_script(
        "window.localStorage.setItem('lnbits.disclaimerShown', 'true')"
    )
    page = context.new_page()
    page.set_default_timeout(60_000)
    try:
        yield page
    finally:
        context.close()


def _complete_first_install(
    base_url: str,
    username: str,
    password: str,
    log_file: Path,
    process: subprocess.Popen,
) -> None:
    payload = {
        "username": username,
        "password": password,
        "password_repeat": password,
        "first_install_token": "",
    }
    deadline = time.monotonic() + 90
    last_error = ""

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"LNbits e2e server exited with {process.returncode}.\n"
                f"{_tail(log_file)}"
            )
        try:
            status, body = request_json(
                f"{base_url}/api/v1/auth/first_install",
                method="PUT",
                data=payload,
                timeout=2,
            )
            if status == 200:
                return
            last_error = f"{status}: {body!r}"
        except (ConnectionError, TimeoutError, URLError, OSError) as exc:
            last_error = repr(exc)
        time.sleep(0.5)

    raise TimeoutError(
        "LNbits e2e server did not complete first install. "
        f"Last error: {last_error}\n{_tail(log_file)}"
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _terminate_process_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=15)


def _tail(path: Path, lines: int = 80) -> str:
    if not path.is_file():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])
