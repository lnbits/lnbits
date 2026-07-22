from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from playwright.sync_api import Frame, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.helpers import LNbitsE2EServer


@dataclass(frozen=True)
class ExtensionUnderTest:
    ext_id: str
    name: str
    manifest_url: str
    repository: str
    permission_texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class E2EWallet:
    id: str
    name: str
    adminkey: str
    inkey: str


def login(page: Page, server: LNbitsE2EServer) -> None:
    page.goto("/")
    page.locator('input[name="username"]').fill(server.username)
    page.locator('input[name="password"]').fill(server.password)
    page.get_by_role("button", name=re.compile("^login$", re.IGNORECASE)).click()
    expect(page).to_have_url(re.compile(r"/wallet/[^/]+$"))
    dismiss_disclaimer(page)


def dismiss_disclaimer(page: Page) -> None:
    try:
        page.get_by_role("button", name="I understand").click(timeout=5_000)
    except PlaywrightTimeoutError:
        pass


def superuser_wallet(page: Page) -> E2EWallet:
    wallet = page.evaluate(
        "() => ({"
        "  adminkey: window.g.user.wallets[0].adminkey,"
        "  id: window.g.user.wallets[0].id,"
        "  inkey: window.g.user.wallets[0].inkey,"
        "  name: window.g.user.wallets[0].name"
        "})"
    )
    return _wallet_from_response(wallet)


def create_wallet(page: Page, name: str) -> E2EWallet:
    wallet = browser_json(
        page,
        "POST",
        "/api/v1/wallet",
        {"name": name},
    )
    return _wallet_from_response(wallet)


def fund_wallet_with_fake_balance(
    page: Page, wallet_id: str, *, amount_sats: int
) -> None:
    response = browser_json(
        page,
        "PUT",
        "/users/api/v1/balance",
        {"id": wallet_id, "amount": amount_sats},
    )
    assert response.get("success") is True, response


def wallet_balance_sat(page: Page, wallet: E2EWallet) -> int:
    response = browser_json(page, "GET", "/api/v1/wallet", api_key=wallet.inkey)
    return int(response["balance"]) // 1000


def wait_for_wallet_balance(
    page: Page,
    wallet: E2EWallet,
    *,
    expected_sats: int,
    timeout: float = 30,
) -> int:
    return int(
        wait_for_result(
            f"wallet {wallet.id} balance to reach {expected_sats} sats",
            lambda: (
                balance
                if (balance := wallet_balance_sat(page, wallet)) >= expected_sats
                else None
            ),
            timeout=timeout,
        )
    )


def create_invoice(
    page: Page,
    wallet: E2EWallet,
    *,
    amount_sats: int,
    memo: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    invoice = browser_json(
        page,
        "POST",
        "/api/v1/payments",
        {
            "out": False,
            "amount": amount_sats,
            "unit": "sat",
            "memo": memo,
            "extra": extra or {},
        },
        api_key=wallet.inkey,
    )
    assert invoice_payment_request(invoice).lower().startswith("lnbc"), invoice
    return invoice


def pay_invoice_with_wallet(
    page: Page, wallet: E2EWallet, payment_request: str
) -> dict[str, Any]:
    return browser_json(
        page,
        "POST",
        "/api/v1/payments",
        {"out": True, "bolt11": payment_request},
        api_key=wallet.adminkey,
    )


def invoice_payment_request(invoice: dict[str, Any]) -> str:
    payment_request = invoice.get("payment_request") or invoice.get("bolt11")
    assert isinstance(payment_request, str), invoice
    return payment_request


def install_and_enable_extension(
    page: Page,
    extension: ExtensionUnderTest,
    *,
    preload_extensions: Sequence[ExtensionUnderTest] = (),
) -> None:
    add_extension_manifests(page, (*preload_extensions, extension))
    install_extension(page, extension)
    enable_extension(page, extension)


def add_extension_manifest(page: Page, extension: ExtensionUnderTest) -> None:
    add_extension_manifests(page, (extension,))


def add_extension_manifests(
    page: Page, extensions: Sequence[ExtensionUnderTest]
) -> None:
    extensions = _unique_extensions(extensions)
    if not extensions:
        return

    page.goto("/admin#extensions")
    dismiss_disclaimer(page)
    saved_manifests = _saved_manifests(page)
    missing_extensions = [
        extension
        for extension in extensions
        if extension.manifest_url not in saved_manifests
    ]

    if missing_extensions:
        manifest_input = (
            page.locator(".q-field")
            .filter(has_text="Source URL")
            .locator("input")
            .first
        )
        for extension in missing_extensions:
            manifest_input.fill(extension.manifest_url)
            manifest_input.press("Enter")
            expect(page.get_by_text(extension.manifest_url)).to_be_visible()
        save_button = page.get_by_role(
            "button", name=re.compile("^save$", re.IGNORECASE)
        )
        expect(save_button).to_be_enabled()
        save_button.click()
        expect(
            page.get_by_text(re.compile("Settings changed", re.IGNORECASE))
        ).to_be_visible()

    saved_manifests = _saved_manifests(page)
    missing_urls = [
        extension.manifest_url
        for extension in extensions
        if extension.manifest_url not in saved_manifests
    ]
    assert not missing_urls, f"Extension manifests were not saved: {missing_urls!r}"


def install_extension(page: Page, extension: ExtensionUnderTest) -> None:
    state = extension_state(page, extension.ext_id)
    if state and state.get("isInstalled"):
        if not state.get("isActive"):
            browser_json(
                page,
                "PUT",
                f"/api/v1/extension/{extension.ext_id}/activate",
            )
            wait_for_installed_extension(page, extension.ext_id)
        return

    browser_json(page, "POST", "/api/v1/extension", _install_payload(extension))
    wait_for_installed_extension(page, extension.ext_id)
    installed = extension_state(page, extension.ext_id)
    granted_permission_ids = {
        permission.get("id") for permission in (installed or {}).get("permissions", [])
    }
    for permission in _latest_release_config(extension).get("permissions") or []:
        assert permission.get("id") in granted_permission_ids


def _install_payload(extension: ExtensionUnderTest) -> dict[str, Any]:
    release = _latest_github_release(extension)
    config = _latest_release_config(extension, release.get("tag_name"))
    version = str(release["tag_name"])
    archive = release.get("zipball_url") or (
        f"https://api.github.com/repos/{extension.repository}/zipball/{version}"
    )
    return {
        "ext_id": extension.ext_id,
        "archive": archive,
        "source_repo": extension.repository,
        "version": version,
        "cost_sats": 0,
        "permissions": config.get("permissions") or [],
    }


def _latest_github_release(extension: ExtensionUnderTest) -> dict[str, Any]:
    release = _fetch_json(
        f"https://api.github.com/repos/{extension.repository}/releases/latest"
    )
    assert isinstance(release, dict), release
    assert release.get("tag_name"), release
    return release


def _latest_release_config(
    extension: ExtensionUnderTest, tag_name: str | None = None
) -> dict[str, Any]:
    tag = tag_name or str(_latest_github_release(extension)["tag_name"])
    config = _fetch_json(
        f"https://raw.githubusercontent.com/{extension.repository}/{tag}/config.json"
    )
    assert isinstance(config, dict), config
    return config


def enable_extension(page: Page, extension: ExtensionUnderTest) -> None:
    page.goto("/extensions")
    page.get_by_role("tab", name=re.compile("^installed$", re.IGNORECASE)).click()
    page.locator(".q-field").filter(has_text="Search extensions").locator("input").fill(
        extension.name
    )
    extension_card = page.locator(".q-card").filter(has_text=extension.name).first
    expect(extension_card).to_be_visible(timeout=120_000)
    enable_button = extension_card.get_by_role(
        "button", name=re.compile("^enable$", re.IGNORECASE)
    )
    if enable_button.is_visible():
        enable_button.click()
        expect(page.get_by_text("Extension enabled!")).to_be_visible(timeout=60_000)
    expect(
        extension_card.get_by_role("link", name=re.compile("^open$", re.IGNORECASE))
    ).to_be_visible(timeout=60_000)


def wait_for_installable_extension(
    page: Page, extension: ExtensionUnderTest, *, timeout: float = 180
) -> None:
    last_response = None
    last_error: Exception | None = None
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            last_error = None
            settings = browser_json(page, "GET", "/admin/api/v1/settings")
            extensions = browser_json(page, "GET", "/api/v1/extension/all")
            last_response = {
                "manifests": settings.get("lnbits_extensions_manifests"),
                "extensions": extensions,
            }
            manifests = settings.get("lnbits_extensions_manifests") or []
            if not isinstance(manifests, list):
                manifests = []
            if not isinstance(extensions, list):
                extensions = []
            if extension.manifest_url in manifests and any(
                item.get("id") == extension.ext_id for item in extensions
            ):
                return
        except Exception as exc:
            last_error = exc
        time.sleep(2)

    raise AssertionError(
        f"{extension.name} extension did not become installable: "
        f"{last_response!r}. Last error: {last_error!r}"
    )


def wait_for_installed_extension(
    page: Page, extension_id: str, *, timeout: float = 120
) -> None:
    def installed_and_active() -> bool:
        state = extension_state(page, extension_id)
        return bool(state and state.get("isInstalled") and state.get("isActive"))

    wait_for_result(
        f"{extension_id} extension to be installed and active",
        lambda: True if installed_and_active() else None,
        timeout=timeout,
        interval=2,
    )


def extension_state(page: Page, extension_id: str) -> dict[str, Any] | None:
    extensions = browser_json(page, "GET", "/api/v1/extension/all")
    assert isinstance(extensions, list), extensions
    extension = next(
        (item for item in extensions if item.get("id") == extension_id),
        None,
    )
    return extension if isinstance(extension, dict) else None


def grant_background_payment_permission(
    page: Page,
    extension_id: str,
    wallet_id: str,
    *,
    max_amount_sats: int,
    destination_policy: str = "external_allowed",
) -> dict[str, Any]:
    return browser_json(
        page,
        "POST",
        f"/api/v1/extension/{extension_id}/permissions/background-payment",
        {
            "wallet_id": wallet_id,
            "max_amount": max_amount_sats,
            "destination_policy": destination_policy,
        },
    )


def grant_wallet_payments_watch_permission(
    page: Page, extension_id: str, wallet_id: str
) -> dict[str, Any]:
    return browser_json(
        page,
        "POST",
        f"/api/v1/extension/{extension_id}/permissions/wallet-payments-watch",
        {"wallet_id": wallet_id},
    )


def extension_api(
    page: Page,
    extension_id: str,
    method: str,
    path: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = browser_json(page, method, f"/api/v1/ext/{extension_id}{path}", data)
    if body.get("ok") is False:
        raise AssertionError(f"{method} {path} failed: {body!r}")
    data = body.get("data", body)
    assert isinstance(data, dict), body
    return data


def browser_json(
    page: Page,
    method: str,
    path: str,
    data: dict[str, Any] | None = None,
    *,
    api_key: str | None = None,
) -> Any:
    response = page.evaluate(
        """async ({method, path, data, apiKey}) => {
          const headers = {'Content-Type': 'application/json'}
          if (apiKey) headers['X-Api-Key'] = apiKey
          const response = await fetch(path, {
            method,
            headers,
            credentials: 'same-origin',
            body: data === null ? undefined : JSON.stringify(data)
          })
          const text = await response.text()
          let body = {}
          try {
            body = text ? JSON.parse(text) : {}
          } catch (error) {
            body = {detail: text}
          }
          return {status: response.status, body}
        }""",
        {"method": method, "path": path, "data": data, "apiKey": api_key},
    )
    status = int(response["status"])
    body = response["body"]
    if not 200 <= status < 300:
        raise AssertionError(f"{method} {path} failed with {status}: {body!r}")
    assert isinstance(body, dict) or isinstance(body, list), body
    return body


def wait_for_result(
    description: str,
    callback: Callable[[], Any | None],
    *,
    timeout: float = 30,
    interval: float = 0.5,
) -> Any:
    deadline = time.monotonic() + timeout
    last_result: Any | None = None
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            last_error = None
            last_result = callback()
            if last_result is not None:
                return last_result
        except Exception as exc:
            last_error = exc
        time.sleep(interval)

    raise AssertionError(
        f"Timed out waiting for {description}. "
        f"Last result: {last_result!r}. Last error: {last_error!r}"
    )


def extension_frame(page: Page, title: str) -> Frame:
    iframe = page.locator(f'iframe[title="{title}"]')
    expect(iframe).to_be_visible(timeout=60_000)
    frame = iframe.element_handle().content_frame()
    assert frame is not None
    return frame


def _manifest_is_saved(page: Page, manifest_url: str) -> bool:
    return manifest_url in _saved_manifests(page)


def _saved_manifests(page: Page) -> list[str]:
    settings = browser_json(page, "GET", "/admin/api/v1/settings")
    manifests = settings.get("lnbits_extensions_manifests") or []
    return manifests if isinstance(manifests, list) else []


def _fetch_json(url: str) -> Any:
    request = Request(  # noqa: S310
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LNbits Playwright e2e",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _unique_extensions(
    extensions: Sequence[ExtensionUnderTest],
) -> tuple[ExtensionUnderTest, ...]:
    unique: list[ExtensionUnderTest] = []
    seen: set[str] = set()
    for extension in extensions:
        if extension.ext_id in seen:
            continue
        unique.append(extension)
        seen.add(extension.ext_id)
    return tuple(unique)


def _wallet_from_response(wallet: Any) -> E2EWallet:
    assert isinstance(wallet, dict), wallet
    return E2EWallet(
        id=str(wallet["id"]),
        name=str(wallet.get("name") or wallet["id"]),
        adminkey=str(wallet["adminkey"]),
        inkey=str(wallet["inkey"]),
    )
