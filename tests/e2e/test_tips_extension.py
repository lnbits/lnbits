from __future__ import annotations

import re
import time
from uuid import uuid4

from playwright.sync_api import (
    Frame,
    Page,
    expect,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from tests.e2e.helpers import LNbitsE2EServer, api_json

TIPS_MANIFEST_URL = (
    "https://raw.githubusercontent.com/lnbits/tips/refs/heads/main/manifest.json"
)


def test_install_tips_extension_and_pay_tip_with_fake_wallet(
    page: Page,
    lnbits_e2e_server: LNbitsE2EServer,
) -> None:
    login(page, lnbits_e2e_server)
    admin_key, wallet_id = superuser_wallet(page)

    add_tips_manifest(page)
    install_tips_extension(page)
    enable_tips_extension(page)
    fund_wallet_with_fake_balance(page, wallet_id, amount_sats=10_000)

    jar_title = f"Playwright Tips {uuid4().hex[:8]}"
    tip_message = f"fake wallet tip {uuid4().hex[:8]}"
    public_url = create_tip_jar(page, jar_title)
    payment_request = create_public_tip_invoice(page, public_url, tip_message)

    api_json(
        lnbits_e2e_server.base_url,
        "POST",
        "/api/v1/payments",
        {"out": True, "bolt11": payment_request},
        api_key=admin_key,
    )

    public_frame = tips_frame(page)
    expect(public_frame.locator("#invoice-status")).to_have_text(
        "Payment received",
        timeout=30_000,
    )

    page.goto("/ext/tips")
    admin_frame = tips_frame(page)
    expect(admin_frame.get_by_role("cell", name=jar_title).first).to_be_visible(
        timeout=60_000
    )
    admin_frame.get_by_role("button", name="Refresh").click()
    expect(admin_frame.get_by_role("cell", name=tip_message).first).to_be_visible(
        timeout=60_000
    )
    expect(admin_frame.get_by_role("cell", name="Paid").first).to_be_visible()


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


def superuser_wallet(page: Page) -> tuple[str, str]:
    wallet = page.evaluate(
        "() => ({"
        "  adminkey: window.g.user.wallets[0].adminkey,"
        "  id: window.g.user.wallets[0].id"
        "})"
    )
    return str(wallet["adminkey"]), str(wallet["id"])


def fund_wallet_with_fake_balance(
    page: Page, wallet_id: str, *, amount_sats: int
) -> None:
    response = page.evaluate(
        """async ({walletId, amountSats}) => {
          const response = await fetch('/users/api/v1/balance', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id: walletId, amount: amountSats})
          })
          const body = await response.json()
          return {status: response.status, body}
        }""",
        {"walletId": wallet_id, "amountSats": amount_sats},
    )
    assert response["status"] == 200, response


def add_tips_manifest(page: Page) -> None:
    page.goto("/admin#extensions")
    dismiss_disclaimer(page)
    manifest_input = (
        page.locator(".q-field").filter(has_text="Source URL").locator("input").first
    )
    manifest_input.fill(TIPS_MANIFEST_URL)
    manifest_input.press("Enter")
    expect(page.get_by_text(TIPS_MANIFEST_URL)).to_be_visible()
    save_button = page.get_by_role("button", name=re.compile("^save$", re.IGNORECASE))
    expect(save_button).to_be_enabled()
    save_button.click()
    expect(
        page.get_by_text(re.compile("Settings changed", re.IGNORECASE))
    ).to_be_visible()
    wait_for_installable_tips(page)


def wait_for_installable_tips(page: Page) -> None:
    deadline = time.monotonic() + 180
    last_response = None

    while time.monotonic() < deadline:
        last_response = page.evaluate("""async () => {
              const settingsResponse = await fetch('/admin/api/v1/settings')
              const settings = await settingsResponse.json()
              const extensionsResponse = await fetch('/api/v1/extension/all')
              const extensions = await extensionsResponse.json()
              return {
                settingsStatus: settingsResponse.status,
                manifests: settings.lnbits_extensions_manifests,
                extensionsStatus: extensionsResponse.status,
                extensions,
              }
            }""")
        manifests = last_response.get("manifests") or []
        extensions = last_response.get("extensions") or []
        if not isinstance(manifests, list):
            manifests = []
        if not isinstance(extensions, list):
            extensions = []
        tips_extension = next(
            (extension for extension in extensions if extension.get("id") == "tips"),
            None,
        )
        if TIPS_MANIFEST_URL in manifests and tips_extension:
            return
        time.sleep(2)

    raise AssertionError(
        "Tips extension did not become installable from the live manifest: "
        f"{last_response!r}"
    )


def install_tips_extension(page: Page) -> None:
    page.goto("/extensions")
    page.get_by_role("tab", name=re.compile("^all$", re.IGNORECASE)).click()
    page.locator(".q-field").filter(has_text="Search extensions").locator("input").fill(
        "Tips"
    )
    tips_card = page.locator(".q-card").filter(
        has_text="Receive Lightning tips with short messages."
    )
    expect(tips_card).to_be_visible(timeout=120_000)
    tips_card.get_by_role("button", name=re.compile("^manage$", re.IGNORECASE)).click()

    dialog = page.locator(".q-dialog").filter(has_text="lnbits/tips")
    expect(dialog).to_be_visible(timeout=120_000)
    repo_card = dialog.locator(".q-card").filter(has_text="lnbits/tips").first
    release = repo_card.locator(".q-list .q-expansion-item").filter(
        has_text=re.compile(r"v\d+\.\d+\.\d+")
    )
    if not release.first.is_visible():
        repo_card.locator(".q-expansion-item .q-item").first.click()
    expect(release.first).to_be_visible(timeout=120_000)
    release.first.locator(".q-item").first.click()
    install_button = release.first.get_by_role(
        "button", name=re.compile("^install$", re.IGNORECASE)
    )
    expect(install_button).to_be_enabled(timeout=120_000)
    install_button.click()

    expect(page.get_by_text("Grant extension permissions")).to_be_visible()
    expect(page.get_by_text("Make background payments")).to_be_visible()
    page.get_by_role("button", name="Grant and install").click()
    expect(page.get_by_text("Grant extension permissions")).not_to_be_visible(
        timeout=180_000
    )
    wait_for_installed_tips(page)


def enable_tips_extension(page: Page) -> None:
    page.goto("/extensions")
    page.get_by_role("tab", name=re.compile("^installed$", re.IGNORECASE)).click()
    page.locator(".q-field").filter(has_text="Search extensions").locator("input").fill(
        "Tips"
    )
    tips_card = page.locator(".q-card").filter(
        has_text="Receive Lightning tips with short messages."
    )
    expect(tips_card).to_be_visible(timeout=120_000)
    enable_button = tips_card.get_by_role(
        "button", name=re.compile("^enable$", re.IGNORECASE)
    )
    if enable_button.is_visible():
        enable_button.click()
        expect(page.get_by_text("Extension enabled!")).to_be_visible(timeout=60_000)
    expect(
        tips_card.get_by_role("link", name=re.compile("^open$", re.IGNORECASE))
    ).to_be_visible(timeout=60_000)


def wait_for_installed_tips(page: Page) -> None:
    deadline = time.monotonic() + 120
    last_extensions = None

    while time.monotonic() < deadline:
        last_extensions = page.evaluate(
            "async () => await (await fetch('/api/v1/extension/all')).json()"
        )
        if isinstance(last_extensions, list):
            tips_extension = next(
                (
                    extension
                    for extension in last_extensions
                    if extension.get("id") == "tips"
                ),
                None,
            )
            if (
                tips_extension
                and tips_extension.get("isInstalled")
                and tips_extension.get("isActive")
            ):
                return
        time.sleep(2)

    raise AssertionError(
        f"Tips extension was not installed and active: {last_extensions!r}"
    )


def create_tip_jar(page: Page, jar_title: str) -> str:
    page.goto("/ext/tips")
    frame = tips_frame(page)
    expect(frame.get_by_text("Create Jar")).to_be_visible(timeout=60_000)
    frame.get_by_label("Title").fill(jar_title)
    frame.get_by_role("button", name=re.compile("^create$", re.IGNORECASE)).click()
    expect(frame.get_by_role("cell", name=jar_title)).to_be_visible(timeout=60_000)
    frame.wait_for_function(
        "() => [...document.querySelectorAll('input')]"
        ".some(input => input.value.includes('/ext/tips/jars/'))"
    )
    public_url = frame.evaluate(
        "() => [...document.querySelectorAll('input')]"
        ".map(input => input.value)"
        ".find(value => value.includes('/ext/tips/jars/'))"
    )
    assert isinstance(public_url, str)
    assert "/ext/tips/jars/" in public_url
    return public_url


def create_public_tip_invoice(page: Page, public_url: str, tip_message: str) -> str:
    page.goto(public_url)
    frame = tips_frame(page)
    expect(frame.get_by_text("Leave a Tip")).to_be_visible(timeout=60_000)
    frame.get_by_label("Name").fill("Playwright")
    frame.get_by_label("Message").fill(tip_message)
    frame.get_by_role("button", name="Create Invoice").click()
    expect(frame.get_by_text("Waiting for payment")).to_be_visible(timeout=60_000)
    frame.wait_for_function(
        "() => Boolean(document.querySelector('#copy-invoice-button')?.dataset.invoice)"
    )
    payment_request = frame.locator("#copy-invoice-button").evaluate(
        "button => button.dataset.invoice"
    )
    assert isinstance(payment_request, str)
    assert payment_request.lower().startswith("lnbc")
    return payment_request


def tips_frame(page: Page) -> Frame:
    iframe = page.locator('iframe[title="Tips"]')
    expect(iframe).to_be_visible(timeout=60_000)
    frame = iframe.element_handle().content_frame()
    assert frame is not None
    return frame
