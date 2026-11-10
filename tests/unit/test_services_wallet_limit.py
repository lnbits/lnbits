from uuid import uuid4

import pytest

from lnbits.core.crud import create_payment, create_wallet
from lnbits.core.models import CreatePayment, PaymentState
from lnbits.core.services import create_user_account
from lnbits.core.services.payments import check_wallet_daily_withdraw_limit
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_no_wallet_limit(settings: Settings):
    settings.lnbits_wallet_limit_daily_max_withdraw = 0
    result = await check_wallet_daily_withdraw_limit(
        conn=None, wallet_id="333333", amount_msat=0
    )

    assert result is None, "No limit set."


@pytest.mark.anyio
async def test_wallet_limit_but_no_payments(settings: Settings):
    settings.lnbits_wallet_limit_daily_max_withdraw = 5
    result = await check_wallet_daily_withdraw_limit(
        conn=None, wallet_id="333333", amount_msat=0
    )

    assert result is None, "Limit not reqached."


@pytest.mark.anyio
async def test_no_wallet_spend_allowed(settings: Settings):
    settings.lnbits_wallet_limit_daily_max_withdraw = -1

    with pytest.raises(
        ValueError, match="It is not allowed to spend funds from this server."
    ):
        await check_wallet_daily_withdraw_limit(
            conn=None, wallet_id="333333", amount_msat=0
        )


async def _create_outgoing_payment(wallet_id: str, status: PaymentState):
    checking_id = f"checking_{uuid4().hex[:8]}"
    await create_payment(
        checking_id=checking_id,
        data=CreatePayment(
            wallet_id=wallet_id,
            payment_hash=uuid4().hex,
            bolt11=f"bolt11-{checking_id}",
            amount_msat=-5_000,
            memo="",
        ),
        status=status,
    )


@pytest.mark.anyio
async def test_failed_payments_do_not_count_towards_limit(app, settings: Settings):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await _create_outgoing_payment(wallet.id, PaymentState.FAILED)
    settings.lnbits_wallet_limit_daily_max_withdraw = 5
    try:
        result = await check_wallet_daily_withdraw_limit(
            conn=None, wallet_id=wallet.id, amount_msat=1_000
        )
    finally:
        settings.lnbits_wallet_limit_daily_max_withdraw = 0

    assert result is None, "Failed payments should not use up the limit."


@pytest.mark.anyio
async def test_successful_payments_count_towards_limit(app, settings: Settings):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await _create_outgoing_payment(wallet.id, PaymentState.SUCCESS)
    settings.lnbits_wallet_limit_daily_max_withdraw = 5
    try:
        with pytest.raises(
            ValueError, match="Daily withdrawal limit of 5 sats reached."
        ):
            await check_wallet_daily_withdraw_limit(
                conn=None, wallet_id=wallet.id, amount_msat=1_000
            )
    finally:
        settings.lnbits_wallet_limit_daily_max_withdraw = 0
