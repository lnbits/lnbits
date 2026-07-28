import json
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
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
from lnurl.types import CallbackUrl, LightningInvoice
from pydantic import parse_obj_as

from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.models import Account, CreateInvoice
from lnbits.core.models.lnurl import CreateLnurlPayment, LnurlScan
from lnbits.core.models.wallets import KeyType, WalletTypeInfo
from lnbits.core.services.lightning_address import wallet_lightning_address_callback
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.services.users import create_user_account
from lnbits.core.views.lnurl_api import (
    api_lnurlscan,
    api_lnurlscan_post,
    api_payments_pay_lnurl,
    api_perform_lnurlauth,
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
async def test_wallet_lightning_address_lookup_and_callback(
    client, to_user, settings, mocker
):
    settings.lnbits_enable_wallet_lightning_addresses = True
    wallet = await create_wallet(user_id=to_user.id, wallet_name="ln address")
    assert wallet.lightning_address

    response = await client.get(f"/.well-known/lnurlp/{wallet.lightning_address}")
    assert response.status_code == 200
    data = response.json()
    metadata = data["metadata"]
    assert data["minSendable"] == 1000
    assert data["maxSendable"] == 2_100_000_000_000_000_000
    assert data["commentAllowed"] == 799
    assert f"{wallet.lightning_address}@" in metadata
    assert "text/identifier" in metadata

    tagged_response = await client.get(
        f"/.well-known/lnurlp/{wallet.lightning_address}+market"
    )
    assert tagged_response.status_code == 200
    tagged_data = tagged_response.json()
    tagged_metadata = json.loads(tagged_data["metadata"])
    assert ["text/tag", "market"] in tagged_metadata
    assert any(
        entry[0] == "text/identifier"
        and entry[1].startswith(f"{wallet.lightning_address}+market@")
        for entry in tagged_metadata
    )

    create_invoice_mock = mocker.patch(
        "lnbits.core.services.payments.create_invoice",
        mocker.AsyncMock(return_value=SimpleNamespace(bolt11=TEST_BOLT11)),
    )
    callback = tagged_data["callback"].split("testserver")[-1]
    callback_response = await client.get(f"{callback}?amount=21000&comment=hello")
    assert callback_response.status_code == 200
    assert callback_response.json()["pr"] == TEST_BOLT11
    create_invoice_mock.assert_awaited_once()
    kwargs = create_invoice_mock.await_args.kwargs
    assert kwargs["wallet_id"] == wallet.id
    assert kwargs["amount"] == 21
    assert kwargs["extra"]["tag"] == "wallet_lightning_address"
    assert kwargs["extra"]["comment"] == "hello"
    assert kwargs["extra"]["lnaddress"].startswith(f"{wallet.lightning_address}+")
    assert kwargs["extra"]["lnaddress_tag"] == "market"


@pytest.mark.anyio
async def test_wallet_lightning_address_generation_settings(to_user, settings):
    settings.lnbits_enable_wallet_lightning_addresses = True
    wallet = await create_wallet(user_id=to_user.id)
    assert wallet.lightning_address
    parts = wallet.lightning_address.split(".")
    assert len(parts) == 3
    assert parts[0].islower()
    assert parts[1].islower()
    assert parts[2].isdigit()
    assert len(parts[2]) == 3

    settings.lnbits_enable_wallet_lightning_addresses = False
    disabled_wallet = await create_wallet(user_id=to_user.id)
    assert disabled_wallet.lightning_address is None

    settings.lnbits_enable_wallet_lightning_addresses = True
    backfilled = await get_wallet(disabled_wallet.id)
    assert backfilled
    assert backfilled.lightning_address


@pytest.mark.anyio
async def test_wallet_lightning_address_callback_validates_comment(
    to_user, settings, mocker
):
    settings.lnbits_enable_wallet_lightning_addresses = True
    wallet = await create_wallet(user_id=to_user.id)
    assert wallet.lightning_address
    request = mocker.Mock()
    request.url.netloc = "example.com"
    request.query_params.get.return_value = "x" * 800

    result = await wallet_lightning_address_callback(
        wallet.lightning_address, request, amount=1000
    )
    assert isinstance(result, LnurlErrorResponse)
    assert "can only accept 799" in result.reason


@pytest.mark.anyio
async def test_lnurl_api_scan_routes_validate_and_forward(mocker):
    pay_response = make_lnurl_pay_response()
    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurl_handle",
        mocker.AsyncMock(return_value=pay_response),
    )

    scanned = await api_lnurlscan("lnurl1example")
    assert isinstance(scanned, LnurlPayResponse)
    assert scanned.callback == pay_response.callback

    scanned_post = await api_lnurlscan_post(
        scan=LnurlScan(lnurl=LnAddress("alice@example.com"))
    )
    assert isinstance(scanned_post, LnurlPayResponse)
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
    pay_response = make_lnurl_pay_response()
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
    assert isinstance(authenticated, LnurlAuthResponse)
    assert authenticated.k1 == "k1-value"

    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurlauth",
        mocker.AsyncMock(side_effect=LnurlResponseException("denied")),
    )
    with pytest.raises(HTTPException, match="denied"):
        await api_perform_lnurlauth(auth_response, wallet_info)

    action_response = LnurlPayActionResponse(
        pr=cast(LightningInvoice, LightningInvoice(TEST_BOLT11)),
        disposable=False,
        successAction=parse_obj_as(MessageAction, {"message": "paid"}),
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
        CreateLnurlPayment(
            res=pay_response, amount=2_000, unit="USD", comment="thanks"
        ),
        wallet_info,
    )
    assert paid.payment_hash == payment.payment_hash
    fetch_mock.assert_awaited_once()
    pay_mock.assert_awaited_once()
    assert pay_mock.await_args is not None
    assert action_response.successAction is not None
    assert pay_mock.await_args.kwargs["extra"] == {
        "stored": True,
        "success_action": action_response.successAction.json(),
        "comment": "thanks",
        "fiat_currency": "USD",
        "fiat_amount": 2.0,
    }

    with pytest.raises(HTTPException, match="Missing LNURL or LnurlPayResponse data."):
        await api_payments_pay_lnurl(CreateLnurlPayment(amount=1), wallet_info)
