from uuid import uuid4

import pytest
from bolt11.types import MilliSatoshi
from lnurl import (
    LnAddress,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlResponseException,
    LnurlSuccessResponse,
    LnurlWithdrawResponse,
)
from lnurl.types import CallbackUrl, LightningInvoice
from pydantic import parse_obj_as
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_account, create_wallet, get_wallet
from lnbits.core.models import Account
from lnbits.core.models.lnurl import CreateLnurlPayment
from lnbits.core.models.wallets import Wallet
from lnbits.core.services.lnurl import (
    fetch_lnurl_pay_request,
    get_pr_from_lnurl,
    perform_withdraw,
    store_paylink,
)
from tests.helpers import make_lnurl_pay_response

TEST_BOLT11 = (
    "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
    "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
    "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
    "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
    "6hjxepwp93cq398l3s"
)


@pytest.mark.anyio
async def test_perform_withdraw_success_and_validation(mocker: MockerFixture):
    withdraw_response = LnurlWithdrawResponse(
        callback=parse_obj_as(CallbackUrl, "https://example.com/callback"),
        k1="k1",
        minWithdrawable=MilliSatoshi(1),
        maxWithdrawable=MilliSatoshi(1000),
        defaultDescription="test",
    )
    execute_withdraw_mock = mocker.patch(
        "lnbits.core.services.lnurl.execute_withdraw",
        mocker.AsyncMock(return_value=LnurlSuccessResponse()),
    )
    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=withdraw_response),
    )

    await perform_withdraw("lnurl", "bolt11")

    execute_withdraw_mock.assert_awaited_once()

    mocker.patch(
        "lnbits.core.services.lnurl.check_callback_url",
        side_effect=ValueError("blocked"),
    )
    with pytest.raises(LnurlResponseException, match="Invalid callback URL"):
        await perform_withdraw("lnurl", "bolt11")


@pytest.mark.anyio
async def test_perform_withdraw_rejects_error_response(mocker: MockerFixture):
    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=LnurlErrorResponse(reason="boom")),
    )

    with pytest.raises(LnurlResponseException, match="boom"):
        await perform_withdraw("lnurl", "bolt11")


@pytest.mark.anyio
async def test_get_pr_from_lnurl_success_and_error(mocker: MockerFixture):
    pay_response = make_lnurl_pay_response(min_sendable_msat=1, text="Test")
    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=pay_response),
    )
    mocker.patch(
        "lnbits.core.services.lnurl.execute_pay_request",
        mocker.AsyncMock(
            return_value=LnurlPayActionResponse(pr=LightningInvoice(TEST_BOLT11))
        ),
    )

    assert await get_pr_from_lnurl("lnurl", 1000, comment="hello") == TEST_BOLT11

    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=LnurlErrorResponse(reason="nope")),
    )
    with pytest.raises(LnurlResponseException, match="nope"):
        await get_pr_from_lnurl("lnurl", 1000)


@pytest.mark.anyio
async def test_fetch_lnurl_pay_request_converts_currency_and_stores_paylink(
    mocker: MockerFixture,
):
    pay_response = make_lnurl_pay_response(min_sendable_msat=1, text="Test")
    action_response = LnurlPayActionResponse(
        pr=LightningInvoice(TEST_BOLT11), disposable=False
    )
    mocker.patch(
        "lnbits.core.services.lnurl.fiat_amount_as_satoshis",
        mocker.AsyncMock(return_value=100),
    )
    execute_mock = mocker.patch(
        "lnbits.core.services.lnurl.execute_pay_request",
        mocker.AsyncMock(return_value=action_response),
    )
    store_paylink_mock = mocker.patch(
        "lnbits.core.services.lnurl.store_paylink",
        mocker.AsyncMock(),
    )
    wallet = _make_wallet()

    data = CreateLnurlPayment(res=pay_response, amount=2500, unit="USD", comment="hi")
    response, action = await fetch_lnurl_pay_request(data, wallet=wallet)

    assert response == pay_response
    assert action == action_response
    execute_mock.assert_awaited_once()
    assert execute_mock.await_args is not None
    assert execute_mock.await_args.kwargs["msat"] == 100_000
    store_paylink_mock.assert_awaited_once_with(
        pay_response, action_response, wallet, None
    )

    with pytest.raises(LnurlResponseException, match="No LNURL pay request provided."):
        await fetch_lnurl_pay_request(CreateLnurlPayment(amount=1))


@pytest.mark.anyio
async def test_store_paylink_appends_and_updates_existing():
    wallet = await _create_wallet()
    pay_response = make_lnurl_pay_response(min_sendable_msat=1, text="Test")
    action_response = LnurlPayActionResponse(
        pr=LightningInvoice(TEST_BOLT11), disposable=False
    )

    await store_paylink(
        pay_response, action_response, wallet, LnAddress("alice@example.com")
    )
    stored_wallet = await get_wallet(wallet.id)

    assert stored_wallet is not None
    assert len(stored_wallet.stored_paylinks.links) == 1
    assert stored_wallet.stored_paylinks.links[0].lnurl == "alice@example.com"

    first_used = stored_wallet.stored_paylinks.links[0].last_used
    await store_paylink(
        pay_response, action_response, wallet, LnAddress("alice@example.com")
    )
    stored_wallet = await get_wallet(wallet.id)

    assert stored_wallet is not None
    assert len(stored_wallet.stored_paylinks.links) == 1
    assert stored_wallet.stored_paylinks.links[0].last_used >= first_used


def _make_wallet() -> Wallet:
    return Wallet(
        id="wallet-id",
        user="user-id",
        name="Wallet",
        adminkey="admin-key",
        inkey="invoice-key",
    )


async def _create_wallet() -> Wallet:
    user_id = uuid4().hex
    await create_account(Account(id=user_id, username=f"user_{user_id[:8]}"))
    return await create_wallet(user_id=user_id, wallet_name="Wallet")
