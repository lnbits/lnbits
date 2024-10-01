import pytest

from lnbits.core.services import check_wallet_daily_withdraw_limit
from lnbits.settings import settings


@pytest.mark.asyncio
async def test_no_wallet_limit():
    settings.lnbits_wallet_limit_daily_max_withdraw = 0
    result = await check_wallet_daily_withdraw_limit(
        conn=None, wallet_id="333333", amount_msat=0
    )

    assert result is None, "No limit set."


@pytest.mark.asyncio
async def test_wallet_limit_but_no_payments():
    settings.lnbits_wallet_limit_daily_max_withdraw = 5
    result = await check_wallet_daily_withdraw_limit(
        conn=None, wallet_id="333333", amount_msat=0
    )

    assert result is None, "Limit not reqached."


@pytest.mark.asyncio
async def test_no_wallet_spend_allowed():
    settings.lnbits_wallet_limit_daily_max_withdraw = -1
    try:

        await check_wallet_daily_withdraw_limit(
            conn=None, wallet_id="333333", amount_msat=0
        )
        raise AssertionError("Should have raised exception.")
    except ValueError as exc:
        assert str(exc) == "It is not allowed to spend funds from this server."
