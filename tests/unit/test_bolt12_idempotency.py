import asyncio
from unittest.mock import AsyncMock

import pytest

from lnbits.core.crud import (
    create_payment,
    create_wallet,
    get_payments,
    get_wallet,
)
from lnbits.core.models import CreatePayment, PaymentState
from lnbits.core.services import create_user_account, pay_offer
from lnbits.core.services.payments import update_wallet_balance
from lnbits.exceptions import PaymentError
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.base import PaymentResponse
from lnbits.wallets.fake import FakeWallet
from tests.helpers import BOLT12_OFFER, BOLT12_OFFER_WITH_DESCRIPTION


@pytest.fixture
async def offer_wallet(app):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)
    return wallet


@pytest.mark.anyio
@pytest.mark.parametrize("amount", [100, 900])
async def test_offer_retry_with_external_id_pays_once(
    offer_wallet, monkeypatch, amount
):
    backend = AsyncMock(wraps=FakeWallet().pay_offer)
    monkeypatch.setattr(FakeWallet, "pay_offer", backend)
    first = await pay_offer(
        wallet_id=offer_wallet.id,
        offer=BOLT12_OFFER,
        amount_sat=amount,
        external_id="order-1",
    )
    retry = await pay_offer(
        wallet_id=offer_wallet.id,
        offer="lightning:" + BOLT12_OFFER.upper(),
        amount_sat=amount,
        external_id="order-1",
    )

    backend.assert_awaited_once()
    assert retry.payment_hash == first.payment_hash
    assert retry.checking_id == first.checking_id
    assert retry.status == first.status == "success"
    assert len(await get_payments(wallet_id=offer_wallet.id, outgoing=True)) == 1
    after = await get_wallet(offer_wallet.id)
    assert after and after.balance_msat == (1000 - amount) * 1000


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["success", "pending", "timeout"])
async def test_concurrent_offer_retries_pay_once(
    offer_wallet, monkeypatch, settings, state
):
    settings.lnbits_funding_source_pay_offer_wait_seconds = 1
    preimage, backend_id = random_secret_and_hash()

    async def pay(*args, **kwargs):
        if state == "timeout":
            await asyncio.Event().wait()
        return PaymentResponse(
            ok=True if state == "success" else None,
            checking_id=backend_id,
            preimage=preimage,
            fee_msat=0,
            payment_request="lni1resolvedinvoice",
        )

    backend = AsyncMock(side_effect=pay)
    monkeypatch.setattr(FakeWallet, "pay_offer", backend)
    first, retry = await asyncio.gather(
        *(
            pay_offer(
                wallet_id=offer_wallet.id,
                offer=BOLT12_OFFER,
                amount_sat=100,
                external_id="order-1",
            )
            for _ in range(2)
        )
    )

    backend.assert_awaited_once()
    assert retry.payment_hash == first.payment_hash
    assert retry.checking_id == first.checking_id
    assert retry.status == first.status
    assert first.success if state == "success" else first.pending
    assert len(await get_payments(wallet_id=offer_wallet.id, outgoing=True)) == 1
    after = await get_wallet(offer_wallet.id)
    assert after and after.balance_msat == (900_000 if state == "success" else 880_000)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changed",
    [
        {"offer": BOLT12_OFFER_WITH_DESCRIPTION},
        {"amount_sat": 101},
        {"memo": "A different note"},
    ],
)
async def test_offer_retry_rejects_changed_details(offer_wallet, monkeypatch, changed):
    backend = AsyncMock(wraps=FakeWallet().pay_offer)
    monkeypatch.setattr(FakeWallet, "pay_offer", backend)
    request = {
        "wallet_id": offer_wallet.id,
        "offer": BOLT12_OFFER,
        "amount_sat": 100,
        "memo": "Thanks",
        "external_id": "order-1",
    }
    await pay_offer(**request)
    with pytest.raises(PaymentError, match="External ID already used"):
        await pay_offer(**{**request, **changed})
    backend.assert_awaited_once()


@pytest.mark.anyio
async def test_failed_offer_retry_does_not_resend(offer_wallet, monkeypatch):
    backend = AsyncMock(return_value=PaymentResponse(ok=False))
    monkeypatch.setattr(FakeWallet, "pay_offer", backend)
    request = {
        "wallet_id": offer_wallet.id,
        "offer": BOLT12_OFFER,
        "amount_sat": 100,
        "external_id": "order-1",
    }
    with pytest.raises(PaymentError, match="Payment failed"):
        await pay_offer(**request)
    with pytest.raises(PaymentError, match="Use a new external_id to retry"):
        await pay_offer(**request)
    backend.assert_awaited_once()

    # A new ID explicitly requests another attempt.
    with pytest.raises(PaymentError, match="Payment failed"):
        await pay_offer(**{**request, "external_id": "order-2"})
    assert backend.await_count == 2
    after = await get_wallet(offer_wallet.id)
    assert after and after.balance_msat == 1_000_000


@pytest.mark.anyio
@pytest.mark.parametrize("second_id", ["order-2", None, ""])
async def test_offer_can_be_paid_again_with_new_or_missing_id(
    offer_wallet, monkeypatch, second_id
):
    backend = AsyncMock(wraps=FakeWallet().pay_offer)
    monkeypatch.setattr(FakeWallet, "pay_offer", backend)
    payments = [
        await pay_offer(
            wallet_id=offer_wallet.id,
            offer=BOLT12_OFFER,
            amount_sat=100,
            external_id=external_id,
        )
        for external_id in ("order-1" if second_id else second_id, second_id)
    ]
    assert backend.await_count == 2
    assert payments[0].payment_hash != payments[1].payment_hash


@pytest.mark.anyio
async def test_offer_external_id_is_scoped_to_outgoing_wallet_payments(
    offer_wallet, monkeypatch
):
    other_wallet = await create_wallet(user_id=offer_wallet.user)
    await update_wallet_balance(other_wallet, 1000)
    _, payment_hash = random_secret_and_hash()
    await create_payment(
        checking_id=payment_hash,
        data=CreatePayment(
            wallet_id=offer_wallet.id,
            payment_hash=payment_hash,
            bolt11="",
            amount_msat=100_000,
            memo="Incoming payment with the same reference",
            external_id="order-1",
        ),
        status=PaymentState.SUCCESS,
    )
    backend = AsyncMock(wraps=FakeWallet().pay_offer)
    monkeypatch.setattr(FakeWallet, "pay_offer", backend)
    payments = [
        await pay_offer(
            wallet_id=wallet.id,
            offer=BOLT12_OFFER,
            amount_sat=100,
            external_id="order-1",
        )
        for wallet in (offer_wallet, other_wallet)
    ]
    assert backend.await_count == 2
    assert payments[0].payment_hash != payments[1].payment_hash
