from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from functools import wraps
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest
from playwright.sync_api import BrowserContext, Frame, Page
from playwright.sync_api import Error as PlaywrightError

from tests.e2e.helpers import LNbitsE2EServer, request_json

_URL_CHANGE_SCRIPT = """
(() => {
  if (window.__lnbitsUrlSnapshotInstalled) return
  window.__lnbitsUrlSnapshotInstalled = true

  const notify = () => {
    try {
      Promise.resolve(window.__lnbitsUrlSnapshot(window.location.href)).catch(() => {})
    } catch (_error) {}
  }

  for (const name of ['pushState', 'replaceState']) {
    const original = window.history[name]
    window.history[name] = function (...args) {
      const result = original.apply(this, args)
      setTimeout(notify, 0)
      return result
    }
  }

  window.addEventListener('hashchange', () => setTimeout(notify, 0))
  window.addEventListener('popstate', () => setTimeout(notify, 0))
  window.addEventListener('DOMContentLoaded', () => setTimeout(notify, 0))
  setTimeout(notify, 0)
})()
"""

_PAGE_METHODS_TO_FLUSH_URL_SCREENSHOTS = (
    "click",
    "dblclick",
    "evaluate",
    "evaluate_handle",
    "fill",
    "focus",
    "get_by_label",
    "get_by_placeholder",
    "get_by_role",
    "get_by_test_id",
    "get_by_text",
    "goto",
    "locator",
    "press",
    "reload",
    "select_option",
    "set_content",
    "wait_for_load_state",
    "wait_for_timeout",
    "wait_for_url",
)


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


@pytest.fixture
def context(
    new_context: Callable[..., BrowserContext],
    lnbits_e2e_server: LNbitsE2EServer,
) -> Iterator[BrowserContext]:
    context = new_context(
        base_url=lnbits_e2e_server.base_url,
        viewport={"width": 1280, "height": 900},
    )
    context.add_init_script(
        "window.localStorage.setItem('lnbits.disclaimerShown', 'true')"
    )
    context.set_default_timeout(60_000)
    try:
        yield context
    finally:
        context.close()


@pytest.fixture
def page(context: BrowserContext, output_path: str) -> Iterator[Page]:
    page = context.new_page()
    recorder = _UrlScreenshotRecorder(page, Path(output_path))
    recorder.install()
    try:
        yield page
    finally:
        recorder.capture_current_url()
        recorder.flush_pending()


class _UrlScreenshotRecorder:
    def __init__(self, page: Page, output_dir: Path) -> None:
        self.page = page
        self.output_dir = output_dir
        self.index = 0
        self.last_queued_url = ""
        self.last_captured_url = ""
        self.pending_urls: list[str] = []
        self.is_flushing = False
        self._wait_for_load_state = page.wait_for_load_state
        self._wait_for_timeout = page.wait_for_timeout
        self._screenshot = page.screenshot

    def install(self) -> None:
        self.page.expose_binding("__lnbitsUrlSnapshot", self._handle_binding)
        self.page.add_init_script(_URL_CHANGE_SCRIPT)
        self.page.on("framenavigated", self._handle_frame_navigation)
        self._patch_page_methods()

    def capture_current_url(self) -> None:
        self._queue_url(self.page.url)

    def _handle_binding(self, _source: dict[str, Any], url: str) -> None:
        self._queue_url(url)

    def _handle_frame_navigation(self, frame: Frame) -> None:
        self._queue_url(frame.url)

    def flush_pending(self) -> None:
        if self.is_flushing or not self.pending_urls:
            return
        if self.page.is_closed():
            return

        self.is_flushing = True
        try:
            pending_urls = self.pending_urls
            self.pending_urls = []
            for url in pending_urls:
                self._capture_url(url)
        finally:
            self.is_flushing = False

    def _queue_url(self, url: str) -> None:
        if not url or url == "about:blank" or url == self.last_queued_url:
            return
        self.last_queued_url = url
        self.pending_urls.append(url)

    def _capture_url(self, url: str) -> None:
        if url == self.last_captured_url:
            return

        self.index += 1
        self.last_captured_url = url
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"url-{self.index:02d}-{_url_slug(url)}.png"
        try:
            self._wait_for_load_state("domcontentloaded", timeout=2_000)
        except PlaywrightError:
            pass
        try:
            self._wait_for_timeout(250)
            self._screenshot(path=path, full_page=True, timeout=5_000)
        except (OSError, PlaywrightError):
            pass

    def _patch_page_methods(self) -> None:
        for method_name in _PAGE_METHODS_TO_FLUSH_URL_SCREENSHOTS:
            original = getattr(self.page, method_name, None)
            if not callable(original):
                continue

            @wraps(original)
            def wrapped(
                *args: Any, __original: Callable[..., Any] = original, **kwargs: Any
            ) -> Any:
                self.flush_pending()
                result = __original(*args, **kwargs)
                self.flush_pending()
                return result

            setattr(self.page, method_name, wrapped)


def _url_slug(url: str) -> str:
    digest = sha256(url.encode()).hexdigest()[:8]
    label = re.sub(r"^[a-z]+://", "", url, flags=re.IGNORECASE)
    label = label.split("?", 1)[0].split("#", 1)[0]
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-._")
    if not label:
        label = "url"
    return f"{label[:80]}-{digest}"


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
