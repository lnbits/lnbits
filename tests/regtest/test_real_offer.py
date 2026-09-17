import asyncio
import hashlib

import pytest

from lnbits.core.crud import get_standalone_payment, get_wallet
from lnbits.core.models import Payment
from lnbits.settings import Settings

from .helpers import funding_source, lookup_offer_invoices

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        funding_source.__class__.__name__
        not in ("CoreLightningWallet", "EclairWallet", "LNbitsWallet"),
        reason="BOLT12 regtest requires CoreLightning, Eclair or LNbits backed by CLN",
    ),
]


@pytest.mark.parametrize(
    "memos",
    [
        (None, None),
        ("", ""),
        ("  Thanks for the coffee! ☕ First payment.  ", "Second payment — merci! ⚡"),
    ],
    ids=["omitted-memo", "empty-memo", "payer-note"],
)
@pytest.mark.parametrize(
    ("real_offer", "amounts"),
    [(100, (100, 100)), (None, (100, 200))],
    indirect=["real_offer"],
    ids=["fixed-amount", "amountless"],
)
async def test_pay_real_offer(
    client,
    real_offer,
    amounts,
    memos,
    from_wallet,
    adminkey_headers_from,
    inkey_headers_from,
    settings: Settings,
):
    # Allow invoice negotiation and settlement to finish in the success path.
    settings.lnbits_funding_source_pay_invoice_wait_seconds = 60
    wallet_before = await get_wallet(from_wallet.id)
    assert wallet_before
    total_debit_msat = 0
    checking_ids: set[str] = set()

    # Offers are reusable: each payment must settle a separate invoice.
    for amount, memo in zip(amounts, memos, strict=True):
        request = {
            "out": True,
            "payment_request": real_offer["bolt12"],
            "amount": amount,
            "unit": "sat",
            "extra": {"internal_memo": "Private regtest memo"},
        }
        if memo is not None:
            request["memo"] = memo
        response = await client.post(
            "/api/v1/payments",
            json=request,
            headers=adminkey_headers_from,
        )
        assert response.status_code < 300, response.text
        payment = Payment(**response.json())
        assert payment.success, response.text
        assert payment.amount == -amount * 1000
        assert payment.extra["bolt12"] is True
        assert payment.checking_id not in checking_ids
        checking_ids.add(payment.checking_id)
        assert payment.preimage
        assert (
            hashlib.sha256(bytes.fromhex(payment.preimage)).hexdigest()
            == payment.checking_id
        )

        stored = await get_standalone_payment(payment.payment_hash)
        assert stored and stored.success
        assert stored.checking_id == payment.checking_id
        assert stored.preimage == payment.preimage
        for result in (payment, stored):
            assert result.memo == (memo or real_offer["description"])
            assert result.extra["internal_memo"] == "Private regtest memo"
            if memo:
                assert result.extra["payer_note"] == memo
                assert (
                    result.extra["bolt12_offer_description"]
                    == real_offer["description"]
                )
            else:
                assert "payer_note" not in result.extra
                assert "bolt12_offer_description" not in result.extra

        status_response = await client.get(
            f"/api/v1/payments/{payment.payment_hash}", headers=inkey_headers_from
        )
        assert status_response.status_code == 200
        assert status_response.json()["paid"] is True

        backend_status = await funding_source.get_payment_status(payment.checking_id)
        assert backend_status.success
        assert backend_status.preimage == payment.preimage
        assert payment.fee == -abs(backend_status.fee_msat or 0)
        total_debit_msat += amount * 1000 + abs(payment.fee)

        received = await asyncio.to_thread(
            lookup_offer_invoices, real_offer["offer_id"]
        )
        invoices = {
            invoice["payment_hash"]: invoice
            for invoice in received["invoices"]
            if invoice["status"] == "paid"
        }
        assert set(invoices) == checking_ids
        invoice = invoices[payment.checking_id]
        assert payment.bolt11 == invoice["bolt12"]
        assert payment.payment_request == invoice["bolt12"]
        assert stored.bolt11 == invoice["bolt12"]
        assert backend_status.payment_request == invoice["bolt12"]
        assert stored.extra["bolt12_offer"] == real_offer["bolt12"]
        assert invoice["amount_received_msat"] == amount * 1000
        assert invoice["payment_preimage"] == payment.preimage
        assert invoice["description"] == real_offer["description"]
        # Eclair accepts the memo locally but cannot transmit a payer note.
        expected_payer_note = (
            None
            if funding_source.__class__.__name__ == "EclairWallet"
            else memo or None
        )
        assert invoice.get("invreq_payer_note") == expected_payer_note

        wallet_after = await get_wallet(from_wallet.id)
        assert wallet_after
        assert (
            wallet_before.balance_msat - wallet_after.balance_msat == total_debit_msat
        )
