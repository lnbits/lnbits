"""Funding-source pay_offer wiring for BOLT12 (lnbits#2581)."""

from unittest.mock import Mock

import httpx
import pytest

from lnbits.wallets.base import Feature, PaymentResponse
from lnbits.wallets.clnrest import CLNRestWallet
from lnbits.wallets.corelightning import CoreLightningWallet
from lnbits.wallets.eclair import EclairWallet
from lnbits.wallets.phoenixd import PhoenixdWallet

VALID_OFFER = "lno1qgsqvgnwgcg35z6ee2h3yczraddm72xrfua9uve2rlrm9deu7xyfzrcgq9qh"


@pytest.mark.anyio
async def test_corelightning_pay_offer_fetchinvoice_then_pay(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def call(method, payload):
        calls.append((method, payload))
        if method == "fetchinvoice":
            return {"invoice": "lni1resolvedinvoice"}
        if method == "pay":
            return {
                "payment_hash": "ab" * 32,
                "payment_preimage": "cd" * 32,
                "amount_msat": 21000,
                "amount_sent_msat": 21100,
            }
        raise AssertionError(f"unexpected method {method}")

    wallet = object.__new__(CoreLightningWallet)
    wallet.ln = Mock()
    wallet.ln.call = call
    wallet.pay = "pay"
    wallet.pay_failure_error_codes = []

    async def run_sync(func):
        return func()

    monkeypatch.setattr("lnbits.wallets.corelightning.run_sync", run_sync)

    response = await wallet.pay_offer(VALID_OFFER, fee_limit_msat=50, amount_msat=21000)
    assert response.ok is True
    assert response.checking_id == "ab" * 32
    assert response.preimage == "cd" * 32
    assert response.fee_msat == -100
    assert calls[0][0] == "fetchinvoice"
    assert calls[0][1] == {"offer": VALID_OFFER, "amount_msat": 21000}
    assert calls[1][0] == "pay"
    assert calls[1][1]["bolt11"] == "lni1resolvedinvoice"
    assert "offer" not in calls[1][1]


@pytest.mark.anyio
async def test_corelightning_pay_offer_fails_without_invoice(monkeypatch):
    wallet = object.__new__(CoreLightningWallet)
    wallet.ln = Mock()
    wallet.ln.call = Mock(return_value={})
    wallet.pay = "pay"

    async def run_sync(func):
        return func()

    monkeypatch.setattr("lnbits.wallets.corelightning.run_sync", run_sync)

    response = await wallet.pay_offer(VALID_OFFER, fee_limit_msat=1, amount_msat=1000)
    assert response.ok is False
    assert response.error_message == "fetchinvoice returned no invoice"


@pytest.mark.anyio
async def test_phoenixd_pay_offer_posts_payoffer():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "paymentHash": "ef" * 32,
                "paymentPreimage": "aa" * 32,
                "routingFeeSat": 1,
            },
        )

    wallet = object.__new__(PhoenixdWallet)
    wallet.endpoint = "http://phoenixd.test"
    wallet.client = httpx.AsyncClient(
        base_url=wallet.endpoint,
        transport=httpx.MockTransport(handler),
    )
    try:
        response = await wallet.pay_offer(
            VALID_OFFER, fee_limit_msat=0, amount_msat=5000
        )
        assert response.ok is True
        assert response.checking_id == "ef" * 32
        assert response.fee_msat == -1000
        assert requests[0].url.path == "/payoffer"
        body = requests[0].content.decode()
        assert "offer=" in body
        assert "amountSat=5" in body
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
async def test_eclair_pay_offer_posts_payoffer():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/payoffer":
            return httpx.Response(
                200,
                json={
                    "type": "payment-sent",
                    "paymentHash": "11" * 32,
                    "paymentPreimage": "22" * 32,
                },
            )
        if request.url.path == "/getsentinfo":
            return httpx.Response(
                200,
                json=[
                    {
                        "status": {
                            "type": "sent",
                            "feesPaid": 12,
                            "paymentPreimage": "22" * 32,
                        }
                    }
                ],
            )
        return httpx.Response(404)

    wallet = object.__new__(EclairWallet)
    wallet.url = "http://eclair.test"
    wallet.client = httpx.AsyncClient(
        base_url=wallet.url,
        transport=httpx.MockTransport(handler),
    )
    try:
        response = await wallet.pay_offer(
            VALID_OFFER, fee_limit_msat=99, amount_msat=21000
        )
        assert response.ok is True
        assert response.checking_id == "11" * 32
        assert response.fee_msat == -12
        assert requests[0].url.path == "/payoffer"
        body = requests[0].content.decode()
        assert "offer=" in body
        assert "amountMsat=21000" in body
        assert "maxFeeMsat=99" in body
    finally:
        await wallet.client.aclose()


def test_supported_wallets_advertise_bolt12():
    assert Feature.bolt12 in (CoreLightningWallet.features or [])
    assert Feature.bolt12 in (CLNRestWallet.features or [])
    assert Feature.bolt12 in (PhoenixdWallet.features or [])
    assert Feature.bolt12 in (EclairWallet.features or [])


@pytest.mark.anyio
async def test_base_wallet_pay_offer_is_unsupported():
    from lnbits.wallets.void import VoidWallet

    wallet = object.__new__(VoidWallet)
    response = await wallet.pay_offer("lno1abc", 0)
    assert isinstance(response, PaymentResponse)
    assert response.ok is False
    assert "not supported" in (response.error_message or "")
