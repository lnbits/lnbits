import json

import httpx
import pytest

from lnbits.wallets.base import Feature
from lnbits.wallets.lnbits import LNbitsWallet

PAYMENT_HASH = "ab" * 32
PREIMAGE = "cd" * 32
BOLT11 = "lnbcrt10u1fakeholdinvoice"


def _wallet(handler) -> LNbitsWallet:
    wallet = object.__new__(LNbitsWallet)
    wallet.endpoint = "http://lnbits.test"
    wallet.client = httpx.AsyncClient(
        base_url=wallet.endpoint, transport=httpx.MockTransport(handler)
    )
    return wallet


def test_lnbits_wallet_advertises_holdinvoice():
    assert Feature.holdinvoice in (LNbitsWallet.features or [])


@pytest.mark.anyio
async def test_lnbits_create_hold_invoice():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            201,
            json={
                "checking_id": PAYMENT_HASH,
                "payment_hash": PAYMENT_HASH,
                "bolt11": BOLT11,
                "preimage": None,
            },
        )

    wallet = _wallet(handler)
    try:
        response = await wallet.create_hold_invoice(
            amount=1000,
            payment_hash=PAYMENT_HASH,
            memo="hold",
            description_hash=bytes.fromhex("ef" * 32),
        )
        assert response.ok is True
        assert response.checking_id == PAYMENT_HASH
        assert response.payment_request == BOLT11
        assert response.preimage is None
        assert requests[0].method == "POST"
        assert requests[0].url.path == "/api/v1/payments"
        assert json.loads(requests[0].content) == {
            "out": False,
            "amount": 1000,
            "memo": "hold",
            "payment_hash": PAYMENT_HASH,
            "description_hash": "ef" * 32,
        }
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
async def test_lnbits_create_hold_invoice_forwards_backend_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            520,
            json={
                "detail": "Hold invoices are not supported by the funding source.",
                "status": "failed",
            },
        )

    wallet = _wallet(handler)
    try:
        response = await wallet.create_hold_invoice(
            amount=1000, payment_hash=PAYMENT_HASH
        )
        assert response.ok is False
        assert (
            response.error_message
            == "Hold invoices are not supported by the funding source."
        )
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
async def test_lnbits_settle_hold_invoice():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "preimage": PREIMAGE})

    wallet = _wallet(handler)
    try:
        response = await wallet.settle_hold_invoice(preimage=PREIMAGE)
        assert response.ok is True
        assert response.preimage == PREIMAGE
        assert requests[0].url.path == "/api/v1/payments/settle"
        assert json.loads(requests[0].content) == {"preimage": PREIMAGE}
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
async def test_lnbits_settle_hold_invoice_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            520, json={"detail": "invoice is still open", "status": "failed"}
        )

    wallet = _wallet(handler)
    try:
        response = await wallet.settle_hold_invoice(preimage=PREIMAGE)
        assert response.ok is False
        assert response.error_message == "invoice is still open"
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
async def test_lnbits_cancel_hold_invoice():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "checking_id": PAYMENT_HASH})

    wallet = _wallet(handler)
    try:
        response = await wallet.cancel_hold_invoice(payment_hash=PAYMENT_HASH)
        assert response.ok is True
        assert response.checking_id == PAYMENT_HASH
        assert requests[0].url.path == "/api/v1/payments/cancel"
        assert json.loads(requests[0].content) == {"payment_hash": PAYMENT_HASH}
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
async def test_lnbits_cancel_hold_invoice_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    wallet = _wallet(handler)
    try:
        response = await wallet.cancel_hold_invoice(payment_hash=PAYMENT_HASH)
        assert response.ok is False
        assert response.error_message == "Unable to connect to http://lnbits.test."
    finally:
        await wallet.client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"paid": True, "preimage": PREIMAGE}, "success"),
        ({"paid": False, "status": "failed"}, "failed"),
        ({"paid": False, "status": "pending"}, "pending"),
        ({"paid": False}, "pending"),
    ],
)
async def test_lnbits_get_invoice_status(body, expected):
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    wallet = _wallet(handler)
    try:
        status = await wallet.get_invoice_status(PAYMENT_HASH)
        assert getattr(status, expected) is True
    finally:
        await wallet.client.aclose()
