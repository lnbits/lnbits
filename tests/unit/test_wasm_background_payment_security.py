from types import SimpleNamespace

import pytest

from lnbits.core.models.wallets import Wallet
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import PayInvoiceRequest, PayLnurlRequest
from lnbits.helpers import sha256s
from lnbits.wallets.fake import FakeWallet


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["invoice", "lnurl", "lnurl_fetch"])
@pytest.mark.parametrize("context", ["event", "schedule", "user", "websocket"])
@pytest.mark.parametrize("owner", ["alice", "bob", None])
async def test_background_payment_requires_invocation_wallet_owner(
    mocker, method, context, owner
):
    wallet = Wallet(
        id="alice-wallet", user="alice", name="Alice", adminkey="unused", inkey="unused"
    )
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=wallet)
    )
    grant_lookup = mocker.patch(
        "lnbits.core.wasm_ext.api.background_payments.get_user_extension",
        mocker.AsyncMock(
            return_value=SimpleNamespace(
                active=True,
                permissions={
                    "wallet.pay_invoice_background": [
                        {
                            "id": "alice-grant",
                            "wallet_id": wallet.id,
                            "enabled": True,
                            "max_amount": 21,
                            "destination_policy": "external_allowed",
                        }
                    ]
                },
            )
        ),
    )
    invoice = await FakeWallet().create_invoice(21)
    payment_request = invoice.payment_request
    assert payment_request
    fetch = mocker.patch(
        "lnbits.core.services.lnurl.fetch_lnurl_pay_request",
        mocker.AsyncMock(
            return_value=(
                SimpleNamespace(),
                SimpleNamespace(pr=payment_request, successAction=None),
            )
        ),
    )
    pay = mocker.patch(
        "lnbits.core.services.payments.pay_invoice",
        mocker.AsyncMock(
            return_value=SimpleNamespace(
                checking_id="checking-id",
                payment_hash="payment-hash",
                status="success",
                amount=-21_000,
                fee=0,
                pending=False,
                success=True,
            )
        ),
    )
    api = ExtensionHostAPI(
        "game",
        ["wallet.pay_invoice_background", "wallet.pay_invoice"],
        context=context,
        owner_id=sha256s(owner) if owner else None,
        user_id=owner if context != "event" else None,
    )

    async def invoke():
        if method == "invoice":
            return await api.wallet_pay_invoice(
                PayInvoiceRequest(
                    wallet_id=wallet.id,
                    payment_request=payment_request,
                    max_sat=21,
                    description="Payout",
                )
            )
        return await api.wallet_pay_lnurl(
            PayLnurlRequest(
                wallet_id=wallet.id,
                lnurl="winner@example.com",
                amount=21,
                currency="sat",
                comment=None,
                description="Payout",
                max_sat=21,
                fetch_only=method == "lnurl_fetch",
            )
        )

    if owner != "alice":
        with pytest.raises(PermissionError):
            await invoke()
        grant_lookup.assert_not_awaited()
        fetch.assert_not_awaited()
        pay.assert_not_awaited()
    else:
        response = await invoke()
        assert response.ok
        if context == "user":
            grant_lookup.assert_not_awaited()
        else:
            grant_lookup.assert_awaited_once_with("alice", "game")
        if method == "lnurl_fetch":
            pay.assert_not_awaited()
        else:
            pay.assert_awaited_once()
            assert pay.await_args.kwargs["wallet_id"] == wallet.id
