"""Funding-source pay_offer wiring for BOLT12 (lnbits#2581)."""

import json
from unittest.mock import Mock
from urllib.parse import parse_qs

import httpx
import pytest

from lnbits.wallets.base import Feature, PaymentResponse
from lnbits.wallets.clnrest import CLNRestWallet
from lnbits.wallets.corelightning import CoreLightningWallet
from lnbits.wallets.eclair import EclairWallet
from lnbits.wallets.fake import FakeWallet
from lnbits.wallets.lnbits import LNbitsWallet
from lnbits.wallets.phoenixd import PhoenixdWallet
from tests.helpers import BOLT12_OFFER

PAYER_NOTE = "  Merci ☕ & = +\n" + "long note " * 100 + "  "

VALID_OFFER = "lno1qgsqvgnwgcg35z6ee2h3yczraddm72xrfua9uve2rlrm9deu7xyfzrcgq9qh"


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", PAYER_NOTE])
async def test_corelightning_pay_offer_fetchinvoice_then_pay(monkeypatch, payer_note):
    calls: list[tuple[str, dict]] = []

    def call(method, payload):
        calls.append((method, payload))
        if method == "fetchinvoice":
            return {"invoice": "lni1resolvedinvoice", "changes": {}}
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

    response = await wallet.pay_offer(
        VALID_OFFER, fee_limit_msat=50, amount_msat=21000, payer_note=payer_note
    )
    assert response.ok is True
    assert response.checking_id == "ab" * 32
    assert response.payment_request == "lni1resolvedinvoice"
    assert response.preimage == "cd" * 32
    assert response.fee_msat == -100
    assert calls[0][0] == "fetchinvoice"
    assert calls[0][1] == {
        "offer": VALID_OFFER,
        "amount_msat": 21000,
        **({"payer_note": payer_note} if payer_note else {}),
    }
    assert calls[1][0] == "pay"
    assert calls[1][1] == {"bolt11": "lni1resolvedinvoice", "maxfee": 50}


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
@pytest.mark.parametrize("payer_note", [None, "", PAYER_NOTE])
async def test_phoenixd_pay_offer_posts_payoffer(payer_note):
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
            VALID_OFFER, fee_limit_msat=0, amount_msat=5000, payer_note=payer_note
        )
        assert response.ok is True
        assert response.payment_request is None
        assert response.checking_id == "ef" * 32
        assert response.fee_msat == -1000
        assert requests[0].url.path == "/payoffer"
        assert parse_qs(requests[0].content.decode()) == {
            "offer": [VALID_OFFER],
            "amountSat": ["5"],
            **({"message": [payer_note]} if payer_note else {}),
        }
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", PAYER_NOTE])
@pytest.mark.parametrize("invoice", [None, "lni1resolvedinvoice"])
async def test_eclair_pay_offer_posts_payoffer(payer_note, invoice):
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
                        "invoice": {"serialized": invoice} if invoice else None,
                        "status": {
                            "type": "sent",
                            "feesPaid": 12,
                            "paymentPreimage": "22" * 32,
                        },
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
            VALID_OFFER, fee_limit_msat=2000, amount_msat=21000, payer_note=payer_note
        )
        assert response.ok is True
        assert response.payment_request == invoice
        assert response.checking_id == "11" * 32
        assert response.checking_id is not None
        status = await wallet.get_payment_status(response.checking_id)
        assert status.payment_request == invoice
        assert response.fee_msat == -12
        assert requests[0].url.path == "/payoffer"
        assert parse_qs(requests[0].content.decode()) == {
            "offer": [VALID_OFFER],
            "blocking": ["true"],
            "amountMsat": ["21000"],
            "maxFeeFlatSat": ["2"],
            "maxFeePct": ["0"],
        }
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", PAYER_NOTE])
@pytest.mark.parametrize("invoice", [None, "lni1resolvedinvoice"])
@pytest.mark.parametrize("status_has_invoice", [False, True])
async def test_lnbits_pay_offer_posts_payments(payer_note, invoice, status_has_invoice):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/payments" and request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "bolt11": invoice,
                    "checking_id": "33" * 32,
                    "payment_hash": "44" * 32,
                    "status": "success",
                    "paid": True,
                    "preimage": "55" * 32,
                    "details": {"fee": -1000},
                },
            )
        if request.url.path.startswith("/api/v1/payments/"):
            return httpx.Response(
                200,
                json={
                    "paid": True,
                    "status": "success",
                    "preimage": "55" * 32,
                    "details": {
                        "fee": -1000,
                        **({"bolt11": invoice} if status_has_invoice else {}),
                    },
                },
            )
        return httpx.Response(404)

    wallet = object.__new__(LNbitsWallet)
    wallet.endpoint = "http://lnbits.test"
    wallet.client = httpx.AsyncClient(
        base_url=wallet.endpoint,
        transport=httpx.MockTransport(handler),
    )
    try:
        response = await wallet.pay_offer(
            VALID_OFFER, fee_limit_msat=0, amount_msat=21000, payer_note=payer_note
        )
        assert response.ok is True
        assert response.payment_request == invoice
        assert response.checking_id == "33" * 32
        assert response.checking_id is not None
        status = await wallet.get_payment_status(response.checking_id)
        assert status.payment_request == (invoice if status_has_invoice else None)
        assert requests[0].url.path == "/api/v1/payments"
        body = json.loads(requests[0].content.decode())
        assert body == {
            "out": True,
            "bolt11": VALID_OFFER,
            "amount": 21,
            "unit": "sat",
            **({"memo": payer_note} if payer_note else {}),
        }
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
async def test_lnbits_pay_offer_requires_amount():
    wallet = object.__new__(LNbitsWallet)
    wallet.endpoint = "http://lnbits.test"
    wallet.client = httpx.AsyncClient(base_url=wallet.endpoint)
    try:
        response = await wallet.pay_offer(VALID_OFFER, fee_limit_msat=0)
        assert response.ok is False
        assert response.error_message == "Amount is required to pay a BOLT12 offer."
    finally:
        await wallet.client.aclose()


def test_supported_wallets_advertise_bolt12():
    assert Feature.bolt12 in (CoreLightningWallet.features or [])
    assert Feature.bolt12 in (CLNRestWallet.features or [])
    assert Feature.bolt12 in (PhoenixdWallet.features or [])
    assert Feature.bolt12 in (EclairWallet.features or [])
    assert Feature.bolt12 in (LNbitsWallet.features or [])


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", PAYER_NOTE])
async def test_base_wallet_pay_offer_is_unsupported(payer_note):
    from lnbits.wallets.void import VoidWallet

    wallet = object.__new__(VoidWallet)
    response = await wallet.pay_offer("lno1abc", 0, payer_note=payer_note)
    assert isinstance(response, PaymentResponse)
    assert response.ok is False
    assert "not supported" in (response.error_message or "")


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", PAYER_NOTE])
async def test_fake_pay_offer_accepts_note(payer_note):
    wallet = FakeWallet()
    response = await wallet.pay_offer(
        BOLT12_OFFER, fee_limit_msat=50, amount_msat=21000, payer_note=payer_note
    )
    assert response.ok is True
    assert response.checking_id
    assert response.preimage
    assert response.payment_request and response.payment_request.startswith("lni1")
    assert wallet.payment_secrets[response.checking_id] == response.preimage
    assert response.checking_id in wallet.paid_invoices


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", PAYER_NOTE])
@pytest.mark.parametrize("renepay", [False, True])
async def test_clnrest_pay_offer_payloads(monkeypatch, settings, payer_note, renepay):
    monkeypatch.setattr(settings, "clnrest_pay_rune", None if renepay else "pay-rune")
    monkeypatch.setattr(
        settings, "clnrest_renepay_rune", "renepay-rune" if renepay else None
    )
    monkeypatch.setattr("lnbits.wallets.clnrest._generate_label", lambda: "offer-test")
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/v1/fetchinvoice":
            return httpx.Response(
                200, json={"invoice": "lni1resolvedinvoice", "changes": {}}
            )
        return httpx.Response(
            200,
            json={
                "status": "complete",
                "payment_hash": "ab" * 32,
                "payment_preimage": "cd" * 32,
                "amount_msat": 21000,
                "amount_sent_msat": 21050,
            },
        )

    wallet = object.__new__(CLNRestWallet)
    wallet.url = "http://clnrest.test"
    wallet.pay_headers = {"rune": "pay-rune"}
    wallet.renepay_headers = {"rune": "renepay-rune"}
    wallet.statuses = {"complete": True}
    async with httpx.AsyncClient(
        base_url=wallet.url, transport=httpx.MockTransport(handler)
    ) as wallet.client:
        response = await wallet.pay_offer(
            VALID_OFFER, fee_limit_msat=50, amount_msat=21000, payer_note=payer_note
        )
    assert response.ok is True
    assert response.checking_id == "ab" * 32
    assert response.payment_request == "lni1resolvedinvoice"
    assert response.preimage == "cd" * 32
    assert response.fee_msat == 50
    assert len(requests) == 2
    assert requests[0].url.path == "/v1/fetchinvoice"
    assert json.loads(requests[0].content) == {
        "offer": VALID_OFFER,
        "amount_msat": 21000,
        **({"payer_note": payer_note} if payer_note else {}),
    }
    assert requests[1].url.path == ("/v1/renepay" if renepay else "/v1/pay")
    assert json.loads(requests[1].content) == {
        "label": "offer-test",
        "maxfee": 50,
        "invstring" if renepay else "bolt11": "lni1resolvedinvoice",
    }
    for request in requests:
        assert request.headers["rune"] == ("renepay-rune" if renepay else "pay-rune")


@pytest.mark.anyio
@pytest.mark.parametrize("invoice", [None, "lni1resolvedinvoice"])
@pytest.mark.parametrize("wallet_class", [CoreLightningWallet, CLNRestWallet])
async def test_cln_offer_status_invoice(wallet_class, invoice):
    checking_id = "ab" * 32
    data = {
        "pays": [
            {
                "payment_hash": checking_id,
                "status": "complete",
                "amount_msat": 21000,
                "amount_sent_msat": 21050,
                "preimage": "cd" * 32,
                **({"bolt12": invoice} if invoice else {}),
            }
        ]
    }
    wallet = object.__new__(wallet_class)
    if isinstance(wallet, CoreLightningWallet):
        wallet.ln = Mock()
        wallet.ln.listpays.return_value = data
        status = await wallet.get_payment_status(checking_id)
    else:
        wallet.readonly_headers = {"rune": "readonly"}

        def handler(request):
            assert request.url.path == "/v1/listpays"
            assert json.loads(request.content) == {"payment_hash": checking_id}
            return httpx.Response(200, json=data)

        async with httpx.AsyncClient(
            base_url="http://clnrest.test", transport=httpx.MockTransport(handler)
        ) as wallet.client:
            status = await wallet.get_payment_status(checking_id)
    assert status.success
    assert status.payment_request == invoice
    assert status.fee_msat is not None
    assert abs(status.fee_msat) == 50
    assert status.preimage == "cd" * 32
