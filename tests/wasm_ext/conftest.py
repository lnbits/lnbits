from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from tests.wasm_ext.helpers import (
    EXTENSION_ID,
    REPO_ROOT,
    SERVER_HOST,
    LiveLNbitsServer,
)


@pytest.fixture(scope="session")
def browser_name() -> str:
    return "chromium"


@pytest.fixture(scope="session")
def lnbits_server(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[LiveLNbitsServer]:
    run_root = tmp_path_factory.mktemp("wasm_ext_e2e")
    data_dir = run_root / "data"
    extensions_root = run_root / "extensions-root"
    extension_target = extensions_root / "extensions" / EXTENSION_ID
    fixture_extension = REPO_ROOT / "tests" / "fixtures" / EXTENSION_ID

    shutil.copytree(fixture_extension, extension_target)

    port = _free_tcp_port()
    base_url = f"http://{SERVER_HOST}:{port}"
    env = {
        **os.environ,
        "AUTH_HTTPS_ONLY": "false",
        "DEBUG": "true",
        "HOST": SERVER_HOST,
        "LNBITS_ADMIN_UI": "true",
        "LNBITS_BACKEND_WALLET_CLASS": "FakeWallet",
        "LNBITS_DATA_FOLDER": str(data_dir),
        "LNBITS_EXTENSIONS_DEACTIVATE_ALL": "false",
        "LNBITS_EXTENSIONS_PATH": str(extensions_root),
        "LNBITS_PATH": str(REPO_ROOT),
        "PORT": str(port),
        "PYTHONUNBUFFERED": "1",
    }

    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "lnbits.__main__:app",
            "--host",
            SERVER_HOST,
            "--port",
            str(port),
            "--loop",
            "asyncio",
            "--log-level",
            "warning",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_first_install_page(process, base_url)
        auth_cookies = _complete_first_install(base_url)
        yield LiveLNbitsServer(base_url=base_url, auth_cookies=auth_cookies)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


@pytest.fixture
def authenticated_page(page: Any, lnbits_server: LiveLNbitsServer) -> Any:
    page.context.add_cookies(lnbits_server.auth_cookies)
    return page


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((SERVER_HOST, 0))
        return int(sock.getsockname()[1])


def _wait_for_first_install_page(
    process: subprocess.Popen[str],
    base_url: str,
) -> None:
    deadline = time.monotonic() + 60
    last_error: Exception | None = None
    with httpx.Client(follow_redirects=False, timeout=2) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"LNbits exited before startup:\n{output}")
            try:
                response = client.get(f"{base_url}/first_install")
                if response.status_code == 200:
                    return
            except httpx.HTTPError as exc:
                last_error = exc
            time.sleep(0.25)

    output = process.stdout.read() if process.stdout else ""
    raise TimeoutError(f"LNbits did not start: {last_error}\n{output}")


def _complete_first_install(base_url: str) -> list[dict[str, Any]]:
    with httpx.Client(base_url=base_url, follow_redirects=False, timeout=10) as client:
        response = client.put(
            "/api/v1/auth/first_install",
            json={
                "username": "wasmtest-admin",
                "password": "secret1234",
                "password_repeat": "secret1234",
            },
        )
        response.raise_for_status()

        enable_response = client.put(f"/api/v1/extension/{EXTENSION_ID}/enable")
        enable_response.raise_for_status()

        return [
            {
                "name": cookie.name,
                "value": cookie.value,
                "url": base_url,
                "secure": cookie.secure,
                "sameSite": "Lax",
            }
            for cookie in client.cookies.jar
        ]
