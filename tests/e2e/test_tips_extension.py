from __future__ import annotations

import re
from uuid import uuid4

from playwright.sync_api import (
    Frame,
    Page,
    expect,
)

from tests.e2e.extension_helpers import (
    extension_frame,
    fund_wallet_with_fake_balance,
    install_and_enable_extension,
    login,
    superuser_wallet,
)
from tests.e2e.helpers import LNbitsE2EServer, api_json
from tests.e2e.live_extensions import LIVE_EXTENSIONS, TIPS


def test_install_tips_extension_and_pay_tip_with_fake_wallet(
    page: Page,
    lnbits_e2e_server: LNbitsE2EServer,
) -> None:
    login(page, lnbits_e2e_server)
    wallet = superuser_wallet(page)

    install_and_enable_extension(page, TIPS, preload_extensions=LIVE_EXTENSIONS)
    fund_wallet_with_fake_balance(page, wallet.id, amount_sats=10_000)

    jar_title = f"Playwright Tips {uuid4().hex[:8]}"
    tip_message = f"fake wallet tip {uuid4().hex[:8]}"
    public_url = create_tip_jar(page, jar_title)
    payment_request = create_public_tip_invoice(page, public_url, tip_message)

    api_json(
        lnbits_e2e_server.base_url,
        "POST",
        "/api/v1/payments",
        {"out": True, "bolt11": payment_request},
        api_key=wallet.adminkey,
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
    return extension_frame(page, "Tips")
