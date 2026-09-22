"""Only confirmed Phoenixd offer payments may become successful debits."""

import httpx
import pytest

from lnbits.core.crud import create_wallet, get_payments, get_wallet
from lnbits.core.services import create_user_account, pay_offer, update_wallet_balance
from lnbits.exceptions import PaymentError
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.phoenixd import PhoenixdWallet
from tests.helpers import BOLT12_OFFER


@pytest.fixture
async def phoenix_offer_response(app, settings, monkeypatch):
    settings.lnbits_reserve_fee_min = 20_000
    settings.lnbits_reserve_fee_percent = 0
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)
    preimage, payment_hash = random_secret_and_hash()
    response = {
        "paymentHash": payment_hash,
        "paymentPreimage": preimage,
        "routingFeeSat": 1,
    }
    backend = object.__new__(PhoenixdWallet)
    backend.endpoint = "http://phoenixd.test"
    async with httpx.AsyncClient(
        base_url=backend.endpoint,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=response)
        ),
    ) as backend.client:
        monkeypatch.setattr(
            "lnbits.core.services.payments.get_funding_source", lambda: backend
        )
        yield wallet, response, backend


@pytest.mark.anyio
@pytest.mark.parametrize("error_field", ["reason", "message"])
@pytest.mark.parametrize("hash_state", ["present", "null", "missing"])
async def test_phoenixd_offer_explicit_failure_refunds(
    phoenix_offer_response, error_field, hash_state
):
    wallet, response, _ = phoenix_offer_response
    response.pop("paymentPreimage")
    response.pop("routingFeeSat")
    response[error_field] = "No route to recipient"
    if hash_state == "null":
        response["paymentHash"] = None
    elif hash_state == "missing":
        response.pop("paymentHash")

    with pytest.raises(PaymentError, match="No route to recipient"):
        await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100)

    stored = await get_payments(wallet_id=wallet.id, outgoing=True)
    assert len(stored) == 1 and stored[0].failed
    after = await get_wallet(wallet.id)
    assert after and after.balance_msat == 1_000_000


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["paymentHash", "paymentPreimage", "routingFeeSat"])
@pytest.mark.parametrize("field_state", ["missing", "null", "empty"])
async def test_phoenixd_offer_incomplete_response_stays_pending(
    phoenix_offer_response, field, field_state
):
    wallet, response, _ = phoenix_offer_response
    if field_state == "missing":
        response.pop(field)
    else:
        response[field] = None if field_state == "null" else ""

    payment = await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100)

    assert payment.pending
    after = await get_wallet(wallet.id)
    assert after and after.balance_msat == 880_000


@pytest.mark.anyio
@pytest.mark.parametrize("routing_fee_sat", [0, 1])
async def test_phoenixd_offer_confirmed_success_debits(
    phoenix_offer_response, routing_fee_sat
):
    wallet, response, _ = phoenix_offer_response
    response["routingFeeSat"] = routing_fee_sat

    payment = await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100)

    assert payment.success
    assert payment.checking_id == response["paymentHash"]
    assert payment.preimage == response["paymentPreimage"]
    assert payment.fee == -routing_fee_sat * 1000
    after = await get_wallet(wallet.id)
    assert after and after.balance_msat == 900_000 - routing_fee_sat * 1000


@pytest.mark.anyio
@pytest.mark.parametrize("error", ["timeout", "disconnect", 400, 500])
async def test_phoenixd_offer_transport_error_stays_pending(
    phoenix_offer_response, monkeypatch, error
):
    wallet, _, backend = phoenix_offer_response

    async def post(*args, **kwargs):
        request = httpx.Request("POST", "http://phoenixd.test/payoffer")
        if error == "timeout":
            raise httpx.ReadTimeout("Response timed out", request=request)
        if error == "disconnect":
            raise httpx.ReadError("Connection lost", request=request)
        return httpx.Response(error, json={"reason": "Backend error"}, request=request)

    monkeypatch.setattr(backend.client, "post", post)
    payment = await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100)

    assert payment.pending
    after = await get_wallet(wallet.id)
    assert after and after.balance_msat == 880_000
