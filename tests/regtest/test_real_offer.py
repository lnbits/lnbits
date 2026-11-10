import asyncio
import hashlib
from uuid import uuid4

import pytest

from lnbits.core.crud import get_payments_paginated, get_standalone_payment, get_wallet
from lnbits.core.models import Payment
from lnbits.settings import Settings
from lnbits.wallets import get_funding_source
from lnbits.wallets.base import PaymentResponse

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
    settings.lnbits_funding_source_pay_offer_wait_seconds = 60
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


@pytest.mark.parametrize("real_offer", [100], indirect=True)
@pytest.mark.parametrize(
    "lose_response", [False, True], ids=["success", "lost-response"]
)
async def test_pay_real_offer_retry_is_idempotent(
    client,
    real_offer,
    lose_response,
    from_wallet,
    adminkey_headers_from,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    settings.lnbits_funding_source_pay_offer_wait_seconds = 60
    wallet_before = await get_wallet(from_wallet.id)
    assert wallet_before
    records_before = await get_payments_paginated(
        wallet_id=from_wallet.id, outgoing=True
    )
    backend = get_funding_source()
    backend_pay_offer = backend.pay_offer
    settled: list[PaymentResponse] = []

    async def pay_offer(*args, **kwargs):
        result = await backend_pay_offer(*args, **kwargs)
        assert result.success, result.error_message
        settled.append(result)
        if lose_response and len(settled) == 1:
            # The real node paid, but LNbits never received the result. Inject the
            # timeout after settlement so this does not depend on network timing.
            raise asyncio.TimeoutError("Simulated lost BOLT12 payment response")
        return result

    monkeypatch.setattr(backend, "pay_offer", pay_offer)
    request = {
        "out": True,
        "payment_request": real_offer["bolt12"],
        "amount": 100,
        "unit": "sat",
        "external_id": uuid4().hex,
    }
    response = await client.post(
        "/api/v1/payments", json=request, headers=adminkey_headers_from
    )
    assert response.status_code == 201, response.text
    first = Payment(**response.json())
    assert first.pending if lose_response else first.success
    assert first.amount == -100_000
    assert first.external_id == request["external_id"]
    assert len(settled) == 1
    if lose_response:
        assert first.checking_id.startswith("temp_offer_")

    wallet_after_first = await get_wallet(from_wallet.id)
    assert wallet_after_first
    assert wallet_before.balance_msat - wallet_after_first.balance_msat == (
        100_000 + abs(first.fee)
    )

    retry_response = await client.post(
        "/api/v1/payments", json=request, headers=adminkey_headers_from
    )
    assert retry_response.status_code == 201, retry_response.text
    retry = Payment(**retry_response.json())
    assert retry.payment_hash == first.payment_hash
    assert retry.checking_id == first.checking_id
    assert retry.status == first.status
    assert len(settled) == 1
    wallet_after_retry = await get_wallet(from_wallet.id)
    assert wallet_after_retry
    assert wallet_after_retry.balance_msat == wallet_after_first.balance_msat
    records = await get_payments_paginated(wallet_id=from_wallet.id, outgoing=True)
    assert records.total == records_before.total + 1

    received = await asyncio.to_thread(lookup_offer_invoices, real_offer["offer_id"])
    paid = [invoice for invoice in received["invoices"] if invoice["status"] == "paid"]
    assert len(paid) == 1
    assert paid[0]["payment_hash"] == settled[0].checking_id
    assert paid[0]["amount_received_msat"] == 100_000

    # A new ID explicitly requests another payment of the reusable offer.
    new_response = await client.post(
        "/api/v1/payments",
        json={**request, "external_id": uuid4().hex},
        headers=adminkey_headers_from,
    )
    assert new_response.status_code == 201, new_response.text
    second = Payment(**new_response.json())
    assert second.success
    assert second.payment_hash != first.payment_hash
    assert second.checking_id != first.checking_id
    assert len(settled) == 2
    wallet_after_second = await get_wallet(from_wallet.id)
    assert wallet_after_second
    assert wallet_after_retry.balance_msat - wallet_after_second.balance_msat == (
        100_000 + abs(second.fee)
    )
    records = await get_payments_paginated(wallet_id=from_wallet.id, outgoing=True)
    assert records.total == records_before.total + 2
    received = await asyncio.to_thread(lookup_offer_invoices, real_offer["offer_id"])
    paid = [invoice for invoice in received["invoices"] if invoice["status"] == "paid"]
    assert len(paid) == 2
    assert {invoice["payment_hash"] for invoice in paid} == {
        result.checking_id for result in settled
    }
    assert all(invoice["amount_received_msat"] == 100_000 for invoice in paid)
