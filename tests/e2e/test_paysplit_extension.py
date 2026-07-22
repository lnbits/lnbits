from __future__ import annotations

from uuid import uuid4

from playwright.sync_api import Page, expect

from tests.e2e.extension_helpers import (
    create_invoice,
    create_wallet,
    extension_api,
    extension_frame,
    fund_wallet_with_fake_balance,
    grant_background_payment_permission,
    grant_wallet_payments_watch_permission,
    install_and_enable_extension,
    invoice_payment_request,
    login,
    pay_invoice_with_wallet,
    wait_for_wallet_balance,
)
from tests.e2e.helpers import LNbitsE2EServer
from tests.e2e.live_extensions import LIVE_EXTENSIONS, PAYSPLIT
from tests.e2e.lnurl_helpers import LNURLPayServer


def test_install_paysplit_and_split_incoming_payment_with_fake_wallet(
    page: Page,
    lnbits_e2e_server: LNbitsE2EServer,
) -> None:
    login(page, lnbits_e2e_server)
    source = create_wallet(page, f"PaySplit source {uuid4().hex[:8]}")
    target = create_wallet(page, f"PaySplit target {uuid4().hex[:8]}")
    payer = create_wallet(page, f"PaySplit payer {uuid4().hex[:8]}")
    fund_wallet_with_fake_balance(page, payer.id, amount_sats=250)

    install_and_enable_extension(page, PAYSPLIT, preload_extensions=LIVE_EXTENSIONS)
    grant_wallet_payments_watch_permission(page, PAYSPLIT.ext_id, source.id)
    grant_background_payment_permission(
        page,
        PAYSPLIT.ext_id,
        source.id,
        max_amount_sats=100,
    )

    with LNURLPayServer(lnbits_e2e_server.base_url, target) as lnurl_server:
        saved = extension_api(
            page,
            PAYSPLIT.ext_id,
            "POST",
            "/sources",
            {
                "enabled": True,
                "maxAmount": 100,
                "targets": [
                    {
                        "alias": "Playwright target",
                        "lnurl": lnurl_server.lnurl,
                        "percent": 25,
                    }
                ],
                "walletId": source.id,
                "walletName": source.name,
            },
        )
        assert saved["source"]["wallet_id"] == source.id
        assert saved["targets"][0]["percent"] == 25

        page.goto("/ext/paysplit")
        frame = extension_frame(page, "PaySplit")
        frame.locator("#walletSelect").select_option(source.id)
        expect(frame.locator(".target-lnurl").first).to_have_value(
            lnurl_server.lnurl,
            timeout=60_000,
        )

        invoice = create_invoice(
            page,
            source,
            amount_sats=100,
            memo="PaySplit Playwright source",
        )
        pay_invoice_with_wallet(page, payer, invoice_payment_request(invoice))
        wait_for_wallet_balance(page, target, expected_sats=25, timeout=45)

    source_config = extension_api(
        page,
        PAYSPLIT.ext_id,
        "GET",
        f"/sources/{source.id}",
    )
    assert source_config["source"]["enabled"] is True
    assert source_config["targets"][0]["alias"] == "Playwright target"
