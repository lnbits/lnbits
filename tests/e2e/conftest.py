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

_UI_CHANGE_SCRIPT = """
(() => {
  if (window.__lnbitsUiSnapshotInstalled) return

  const visibleElements = new WeakSet()
  let nextSnapshot = 0
  let scheduled = false

  const groups = [
    { kind: 'dialog', selector: '.q-dialog, [role="dialog"]' },
    { kind: 'toast', selector: '.q-notification' }
  ]

  const isVisible = element => {
    if (!(element instanceof HTMLElement)) return false
    if (element.getAttribute('aria-hidden') === 'true') return false
    if (element.classList.contains('q-dialog--hidden')) return false

    const style = window.getComputedStyle(element)
    if (
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      style.opacity === '0'
    ) {
      return false
    }

    const rect = element.getBoundingClientRect()
    return rect.width > 0 && rect.height > 0
  }

  const labelFor = element => (
    element.getAttribute('aria-label') ||
    element.innerText ||
    element.textContent ||
    ''
  ).replace(/\\s+/g, ' ').trim().slice(0, 120)

  const notify = (kind, element) => {
    const snapshotId = `${kind}-${Date.now()}-${++nextSnapshot}`
    const payload = {
      kind,
      snapshotId,
      label: labelFor(element),
      url: window.location.href
    }
    setTimeout(() => {
      try {
        Promise.resolve(window.__lnbitsUiSnapshot(payload)).catch(() => {})
      } catch (_error) {}
    }, 150)
  }

  const scan = () => {
    for (const group of groups) {
      for (const element of document.querySelectorAll(group.selector)) {
        if (isVisible(element)) {
          if (!visibleElements.has(element)) {
            visibleElements.add(element)
            notify(group.kind, element)
          }
        } else {
          visibleElements.delete(element)
        }
      }
    }
  }

  const schedule = () => {
    if (scheduled) return
    scheduled = true
    requestAnimationFrame(() => {
      scheduled = false
      scan()
    })
  }

  const install = () => {
    if (window.__lnbitsUiSnapshotInstalled || !document.documentElement) return
    window.__lnbitsUiSnapshotInstalled = true
    new MutationObserver(schedule).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['aria-hidden', 'class', 'style'],
      childList: true,
      subtree: true
    })
    schedule()
  }

  window.addEventListener('DOMContentLoaded', install)
  setTimeout(install, 0)
})()
"""

_METHODS_TO_FLUSH_SCREENSHOTS = (
    "blur",
    "check",
    "click",
    "dblclick",
    "evaluate",
    "evaluate_handle",
    "fill",
    "filter",
    "focus",
    "get_by_label",
    "get_by_placeholder",
    "get_by_role",
    "get_by_test_id",
    "get_by_text",
    "goto",
    "hover",
    "locator",
    "press",
    "reload",
    "scroll_into_view_if_needed",
    "select_option",
    "set_content",
    "set_input_files",
    "uncheck",
    "wait_for",
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
    recorder = _E2EScreenshotRecorder(page, Path(output_path))
    recorder.install()
    try:
        yield page
    finally:
        recorder.capture_current_url()
        recorder.flush_pending()


class _E2EScreenshotRecorder:
    def __init__(self, page: Page, output_dir: Path) -> None:
        self.page = page
        self.output_dir = output_dir
        self.url_index = 0
        self.ui_index = 0
        self.last_queued_url = ""
        self.last_captured_url = ""
        self.last_queued_ui_snapshot = ""
        self.pending_urls: list[str] = []
        self.pending_ui_snapshots: list[dict[str, str]] = []
        self.is_flushing = False
        self.patched_objects: set[int] = set()
        self._wait_for_load_state = page.wait_for_load_state
        self._wait_for_timeout = page.wait_for_timeout
        self._screenshot = page.screenshot

    def install(self) -> None:
        self.page.expose_binding("__lnbitsUrlSnapshot", self._handle_binding)
        self.page.expose_binding("__lnbitsUiSnapshot", self._handle_ui_binding)
        self.page.add_init_script(_URL_CHANGE_SCRIPT)
        self.page.add_init_script(_UI_CHANGE_SCRIPT)
        self.page.on("frameattached", self._handle_frame_attached)
        self.page.on("framenavigated", self._handle_frame_navigation)
        self._patch_object_methods(self.page)
        for frame in self.page.frames:
            self._patch_object_methods(frame)

    def capture_current_url(self) -> None:
        self._queue_url(self.page.url)

    def _handle_binding(self, _source: dict[str, Any], url: str) -> None:
        self._queue_url(url)

    def _handle_ui_binding(self, source: dict[str, Any], payload: Any) -> None:
        if not isinstance(payload, dict):
            return

        kind = str(payload.get("kind") or "")
        if kind not in {"dialog", "toast"}:
            return

        frame = source.get("frame")
        frame_url = getattr(frame, "url", "") if frame is not None else ""
        snapshot = {
            "kind": kind,
            "snapshot_id": str(payload.get("snapshotId") or ""),
            "label": str(payload.get("label") or kind),
            "url": str(payload.get("url") or frame_url or self.page.url),
        }
        self._queue_ui_snapshot(snapshot)

    def _handle_frame_attached(self, frame: Frame) -> None:
        self._patch_object_methods(frame)

    def _handle_frame_navigation(self, frame: Frame) -> None:
        self._queue_url(frame.url)
        self._patch_object_methods(frame)

    def flush_pending(self) -> None:
        if self.is_flushing:
            return
        if not self.pending_urls and not self.pending_ui_snapshots:
            return
        if self.page.is_closed():
            return

        self.is_flushing = True
        try:
            pending_urls = self.pending_urls
            pending_ui_snapshots = self.pending_ui_snapshots
            self.pending_urls = []
            self.pending_ui_snapshots = []
            for url in pending_urls:
                self._capture_url(url)
            for snapshot in pending_ui_snapshots:
                self._capture_ui_snapshot(snapshot)
        finally:
            self.is_flushing = False

    def _queue_url(self, url: str) -> None:
        if not url or url == "about:blank" or url == self.last_queued_url:
            return
        self.last_queued_url = url
        self.pending_urls.append(url)

    def _queue_ui_snapshot(self, snapshot: dict[str, str]) -> None:
        snapshot_key = "|".join(
            (
                snapshot["kind"],
                snapshot["snapshot_id"],
                snapshot["url"],
                snapshot["label"],
            )
        )
        if snapshot_key == self.last_queued_ui_snapshot:
            return
        self.last_queued_ui_snapshot = snapshot_key
        self.pending_ui_snapshots.append(snapshot)

    def _capture_url(self, url: str) -> None:
        if url == self.last_captured_url:
            return

        self.url_index += 1
        self.last_captured_url = url
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"url-{self.url_index:02d}-{_url_slug(url)}.png"
        try:
            self._wait_for_load_state("domcontentloaded", timeout=2_000)
        except PlaywrightError:
            pass
        try:
            self._wait_for_timeout(250)
            self._screenshot(path=path, full_page=True, timeout=5_000)
        except (OSError, PlaywrightError):
            pass

    def _capture_ui_snapshot(self, snapshot: dict[str, str]) -> None:
        if self.page.is_closed():
            return

        self.ui_index += 1
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = (
            self.output_dir
            / f"{snapshot['kind']}-{self.ui_index:02d}-{_ui_slug(snapshot)}.png"
        )
        try:
            self._wait_for_timeout(250)
            self._screenshot(path=path, full_page=True, timeout=5_000)
        except (OSError, PlaywrightError):
            pass

    def _patch_object_methods(self, target: Any) -> Any:
        if target is None or isinstance(
            target, (bool, bytes, dict, float, int, list, set, str, tuple)
        ):
            return target

        object_id = id(target)
        if object_id in self.patched_objects:
            return target

        self.patched_objects.add(object_id)
        for method_name in _METHODS_TO_FLUSH_SCREENSHOTS:
            original = getattr(target, method_name, None)
            if not callable(original):
                continue

            @wraps(original)
            def wrapped(
                *args: Any, __original: Callable[..., Any] = original, **kwargs: Any
            ) -> Any:
                self.flush_pending()
                result = __original(*args, **kwargs)
                self._patch_object_methods(result)
                self.flush_pending()
                return result

            try:
                setattr(target, method_name, wrapped)
            except (AttributeError, TypeError):
                pass
        return target


def _url_slug(url: str) -> str:
    digest = sha256(url.encode()).hexdigest()[:8]
    label = re.sub(r"^[a-z]+://", "", url, flags=re.IGNORECASE)
    label = label.split("?", 1)[0].split("#", 1)[0]
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-._")
    if not label:
        label = "url"
    return f"{label[:80]}-{digest}"


def _ui_slug(snapshot: dict[str, str]) -> str:
    digest = sha256(
        "|".join(
            (
                snapshot["kind"],
                snapshot["snapshot_id"],
                snapshot["url"],
                snapshot["label"],
            )
        ).encode()
    ).hexdigest()[:8]
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", snapshot["label"]).strip("-._")
    if not label:
        label = snapshot["kind"]
    return f"{label[:60]}-{digest}"


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
