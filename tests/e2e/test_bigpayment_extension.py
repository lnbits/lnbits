from __future__ import annotations

from uuid import uuid4

from playwright.sync_api import Page, expect

from tests.e2e.extension_helpers import (
    create_invoice,
    create_wallet,
    extension_api,
    extension_frame,
    fund_wallet_with_fake_balance,
    install_and_enable_extension,
    invoice_payment_request,
    login,
    wait_for_wallet_balance,
)
from tests.e2e.helpers import LNbitsE2EServer
from tests.e2e.live_extensions import BIGPAYMENT, LIVE_EXTENSIONS


def test_install_bigpayment_and_pay_large_invoice_with_fake_wallet(
    page: Page,
    lnbits_e2e_server: LNbitsE2EServer,
) -> None:
    login(page, lnbits_e2e_server)
    install_and_enable_extension(page, BIGPAYMENT, preload_extensions=LIVE_EXTENSIONS)

    collector = create_wallet(page, f"BigPayment collector {uuid4().hex[:8]}")
    source = create_wallet(page, f"BigPayment source {uuid4().hex[:8]}")
    recipient = create_wallet(page, f"BigPayment recipient {uuid4().hex[:8]}")
    fund_wallet_with_fake_balance(page, source.id, amount_sats=750)

    page.goto("/ext/bigpayment")
    frame = extension_frame(page, "BigPayment")
    expect(frame.get_by_text("Pay large Lightning invoices")).to_be_visible(
        timeout=60_000
    )

    invoice = create_invoice(
        page,
        recipient,
        amount_sats=500,
        memo="BigPayment Playwright recipient",
    )
    selection = extension_api(
        page,
        BIGPAYMENT.ext_id,
        "POST",
        "/selection",
        {
            "walletIds": [collector.id, source.id],
            "collectorWalletId": collector.id,
        },
    )
    assert selection["collectorWalletId"] == collector.id

    payment = extension_api(
        page,
        BIGPAYMENT.ext_id,
        "POST",
        "/payments",
        {
            "paymentRequest": invoice_payment_request(invoice),
            "walletIds": [collector.id, source.id],
            "collectorWalletId": collector.id,
            "memo": "BigPayment Playwright payment",
        },
    )
    assert payment["paid"] is True, payment
    assert payment["direct"] is False, payment
    assert payment["amountSat"] == 500, payment
    assert payment["transfers"][0]["fromWalletId"] == source.id, payment
    wait_for_wallet_balance(page, recipient, expected_sats=500)
