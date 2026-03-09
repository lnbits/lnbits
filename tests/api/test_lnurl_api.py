from uuid import uuid4

import pytest
from bolt11.types import MilliSatoshi
from fastapi import HTTPException
from lnurl import (
    LnAddress,
    LnurlAuthResponse,
    LnurlErrorResponse,
    LnurlException,
    LnurlPayActionResponse,
    LnurlPayResponse,
    LnurlResponseException,
)
from lnurl.models import MessageAction
from lnurl.types import CallbackUrl, LightningInvoice, LnurlPayMetadata
from pydantic import parse_obj_as

from lnbits.core.models import Account, CreateInvoice
from lnbits.core.models.lnurl import CreateLnurlPayment, LnurlScan
from lnbits.core.models.wallets import KeyType, WalletTypeInfo
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.views.lnurl_api import (
    api_lnurlscan,
    api_lnurlscan_post,
    api_payments_pay_lnurl,
    api_perform_lnurlauth,
)
from lnbits.core.services.users import create_user_account

TEST_BOLT11 = (
    "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
    "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
    "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
    "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
    "6hjxepwp93cq398l3s"
)


def _pay_response() -> LnurlPayResponse:
    return LnurlPayResponse(
        callback=parse_obj_as(CallbackUrl, "https://example.com/callback"),
        minSendable=MilliSatoshi(1_000),
        maxSendable=MilliSatoshi(10_000),
        metadata=LnurlPayMetadata(
            '[["text/plain","Test payment"],["text/identifier","alice@example.com"]]'
        ),
    )


@pytest.mark.anyio
async def test_lnurl_api_scan_routes_validate_and_forward(mocker):
    pay_response = _pay_response()
    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurl_handle",
        mocker.AsyncMock(return_value=pay_response),
    )

    scanned = await api_lnurlscan("lnurl1example")
    assert scanned.callback == pay_response.callback

    scanned_post = await api_lnurlscan_post(scan=LnurlScan(lnurl=LnAddress("alice@example.com")))
    assert scanned_post.callback == pay_response.callback

    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurl_handle",
        mocker.AsyncMock(return_value=LnurlErrorResponse(reason="blocked callback")),
    )
    with pytest.raises(HTTPException, match="blocked callback"):
        await api_lnurlscan("lnurl1blocked")

    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurl_handle",
        mocker.AsyncMock(side_effect=LnurlException("invalid lnurl")),
    )
    with pytest.raises(HTTPException, match="invalid lnurl"):
        await api_lnurlscan("lnurl1invalid")


@pytest.mark.anyio
async def test_lnurl_api_auth_and_pay_flow(mocker):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]
    wallet_info = WalletTypeInfo(key_type=KeyType.admin, wallet=wallet)
    pay_response = _pay_response()
    payment = await create_wallet_invoice(
        wallet.id, CreateInvoice(out=False, amount=21, memo="lnurl")
    )

    auth_response = LnurlAuthResponse(
        callback=parse_obj_as(CallbackUrl, "https://example.com/auth"),
        k1="k1-value",
    )
    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurlauth",
        mocker.AsyncMock(return_value=auth_response),
    )
    authenticated = await api_perform_lnurlauth(auth_response, wallet_info)
    assert authenticated.k1 == "k1-value"

    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurlauth",
        mocker.AsyncMock(side_effect=LnurlResponseException("denied")),
    )
    with pytest.raises(HTTPException, match="denied"):
        await api_perform_lnurlauth(auth_response, wallet_info)

    action_response = LnurlPayActionResponse(
        pr=LightningInvoice(TEST_BOLT11),
        disposable=False,
        successAction=MessageAction(message="paid"),
    )
    fetch_mock = mocker.patch(
        "lnbits.core.views.lnurl_api.fetch_lnurl_pay_request",
        mocker.AsyncMock(return_value=(pay_response, action_response)),
    )
    pay_mock = mocker.patch(
        "lnbits.core.views.lnurl_api.pay_invoice",
        mocker.AsyncMock(return_value=payment),
    )

    paid = await api_payments_pay_lnurl(
        CreateLnurlPayment(res=pay_response, amount=2_000, unit="USD", comment="thanks"),
        wallet_info,
    )
    assert paid.payment_hash == payment.payment_hash
    fetch_mock.assert_awaited_once()
    pay_mock.assert_awaited_once()
    assert pay_mock.await_args is not None
    assert pay_mock.await_args.kwargs["extra"] == {
        "stored": True,
        "success_action": action_response.successAction.json(),
        "comment": "thanks",
        "fiat_currency": "USD",
        "fiat_amount": 2.0,
    }

    with pytest.raises(HTTPException, match="Missing LNURL or LnurlPayResponse data."):
        await api_payments_pay_lnurl(CreateLnurlPayment(amount=1), wallet_info)
