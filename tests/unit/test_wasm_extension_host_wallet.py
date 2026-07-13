from types import SimpleNamespace

import pytest

from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import PayInvoiceRequest


@pytest.mark.anyio
async def test_wasm_wallet_pay_invoice_resolves_ln_address(mocker):
    calls = {}

    async def get_wallet(wallet_id: str):
        calls["get_wallet"] = wallet_id
        return SimpleNamespace(user="user1")

    async def get_pr_from_lnurl(lnurl: str, amount_msat: int, comment: str | None):
        calls["lnurl"] = (lnurl, amount_msat, comment)
        return "lnbc1resolved"

    async def pay_invoice(**kwargs):
        calls["pay_invoice"] = kwargs
        return SimpleNamespace(
            checking_id="checking",
            payment_hash="hash",
            status="success",
            amount=-21_000,
            fee=-10,
            pending=False,
            success=True,
        )

    mocker.patch("lnbits.core.crud.wallets.get_wallet", get_wallet)
    mocker.patch("lnbits.core.services.lnurl.get_pr_from_lnurl", get_pr_from_lnurl)
    mocker.patch("lnbits.core.services.payments.pay_invoice", pay_invoice)

    api = ExtensionHostAPI("demoext", ["wallet.pay_invoice"], user_id="user1")
    response = await api.wallet_pay_invoice(
        PayInvoiceRequest(
            wallet_id="wallet1",
            payment_request="alice@example.com",
            max_sat=21,
            description="winner",
        )
    )

    assert response.ok is True
    assert response.checking_id == "checking"
    assert calls["get_wallet"] == "wallet1"
    assert calls["lnurl"] == ("alice@example.com", 21_000, "winner")
    assert calls["pay_invoice"]["payment_request"] == "lnbc1resolved"
    assert calls["pay_invoice"]["max_sat"] == 21


@pytest.mark.anyio
async def test_wasm_wallet_pay_invoice_allows_event_wallet_only(mocker):
    async def get_wallet(wallet_id: str):
        return SimpleNamespace(user="other-user")

    async def pay_invoice(**kwargs):
        return SimpleNamespace(
            checking_id="checking",
            payment_hash="hash",
            status="success",
            amount=-1_000,
            fee=0,
            pending=False,
            success=True,
        )

    mocker.patch("lnbits.core.crud.wallets.get_wallet", get_wallet)
    mocker.patch("lnbits.core.services.payments.pay_invoice", pay_invoice)

    api = ExtensionHostAPI(
        "demoext",
        ["wallet.pay_invoice"],
        context="event",
        owner_id="owner",
        wallet_id="wallet1",
    )
    allowed = await api.wallet_pay_invoice(
        PayInvoiceRequest(
            wallet_id="wallet1",
            payment_request="lnbc1invoice",
            max_sat=None,
            description="",
        )
    )

    assert allowed.ok is True

    with pytest.raises(PermissionError, match="authenticated user context"):
        await api.wallet_pay_invoice(
            PayInvoiceRequest(
                wallet_id="wallet2",
                payment_request="lnbc1invoice",
                max_sat=None,
                description="",
            )
        )
