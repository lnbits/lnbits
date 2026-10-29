import asyncio
from unittest.mock import AsyncMock

import pytest

from lnbits.core.crud import create_wallet, get_standalone_payment, get_wallet
from lnbits.core.services import create_user_account, pay_offer
from lnbits.core.services.payments import (
    check_payment_status,
    update_pending_payment,
    update_wallet_balance,
)
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.base import (
    PaymentFailedStatus,
    PaymentResponse,
    PaymentSuccessStatus,
)
from lnbits.wallets.fake import FakeWallet
from tests.helpers import BOLT12_OFFER


@pytest.fixture
async def offer_wallet(app):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)
    return wallet


@pytest.mark.anyio
@pytest.mark.parametrize("timeout", [False, True])
async def test_bolt12_lost_response_does_not_refund(
    offer_wallet, client, settings, monkeypatch, timeout
):
    settings.lnbits_funding_source_pay_offer_wait_seconds = 1
    settled = asyncio.Event()

    async def pay(*args, **kwargs):
        # The node settled the payment but its response never reached LNbits.
        settled.set()
        if timeout:
            await asyncio.Event().wait()
        return PaymentResponse()

    monkeypatch.setattr(FakeWallet, "pay_offer", pay)
    lookup = AsyncMock(return_value=PaymentFailedStatus())
    monkeypatch.setattr(FakeWallet, "get_payment_status", lookup)
    payment = await pay_offer(
        wallet_id=offer_wallet.id, offer=BOLT12_OFFER, amount_sat=100
    )
    assert settled.is_set()
    assert payment.checking_id == f"temp_offer_{payment.payment_hash}"
    assert len(payment.payment_hash) == 64

    # Reload persisted state, as after a restart with no surviving backend task.
    stored = await get_standalone_payment(payment.payment_hash)
    assert stored and stored.pending
    reserved = await get_wallet(offer_wallet.id)
    assert reserved and reserved.balance_msat == 880_000
    assert (await update_pending_payment(stored)).pending
    response = await client.get(
        f"/api/v1/payments/{payment.payment_hash}",
        headers={"X-Api-Key": offer_wallet.inkey},
    )
    assert response.status_code == 200
    assert response.json()["details"]["status"] == "pending"
    lookup.assert_not_awaited()
    after = await get_wallet(offer_wallet.id)
    assert after and after.balance_msat == reserved.balance_msat


@pytest.mark.anyio
@pytest.mark.parametrize("success", [False, True])
async def test_bolt12_real_backend_reference_can_be_reconciled(
    offer_wallet, monkeypatch, success
):
    preimage, backend_id = random_secret_and_hash()
    monkeypatch.setattr(
        FakeWallet,
        "pay_offer",
        AsyncMock(return_value=PaymentResponse(checking_id=backend_id)),
    )
    status = (
        PaymentSuccessStatus(fee_msat=123, preimage=preimage)
        if success
        else PaymentFailedStatus()
    )
    lookup = AsyncMock(return_value=status)
    monkeypatch.setattr(FakeWallet, "get_payment_status", lookup)
    payment = await pay_offer(
        wallet_id=offer_wallet.id, offer=BOLT12_OFFER, amount_sat=100
    )
    assert payment.pending and payment.checking_id == backend_id
    stored = await get_standalone_payment(payment.payment_hash)
    assert stored
    stored = await update_pending_payment(stored)
    lookup.assert_awaited_once_with(backend_id)
    assert stored.success if success else stored.failed
    after = await get_wallet(offer_wallet.id)
    assert after and after.balance_msat == (899_877 if success else 1_000_000)


@pytest.mark.anyio
async def test_bolt12_guard_does_not_change_bolt11_status_checks(
    offer_wallet, monkeypatch
):
    monkeypatch.setattr(
        FakeWallet, "pay_offer", AsyncMock(return_value=PaymentResponse())
    )
    payment = await pay_offer(
        wallet_id=offer_wallet.id, offer=BOLT12_OFFER, amount_sat=100
    )
    # BOLT11 hashes are genuine backend references even with caller-supplied extra.
    payment.bolt11 = "lnbc1invoice"
    payment.checking_id = payment.payment_hash
    payment.extra = {"bolt12": True, "bolt12_offer": BOLT12_OFFER}
    lookup = AsyncMock(return_value=PaymentFailedStatus())
    monkeypatch.setattr(FakeWallet, "get_payment_status", lookup)
    assert (await check_payment_status(payment)).failed
    lookup.assert_awaited_once_with(payment.payment_hash)
