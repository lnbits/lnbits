"""Contract and failure-mode tests for the Clavestra funding source.

The JSON fixtures in ``fixtures/clavestra-v15`` are copied byte-for-byte from
clavestra-gateway commit a9ffff253cfb6848e08a180dbebb31bd6ca11574.
HTTP uses ``httpx.MockTransport`` deliberately: these tests must not replace the
session-wide pytest-httpserver port fixture used by the other wallet tests.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from lnbits.exceptions import UnsupportedError
from lnbits.settings import settings
from lnbits.wallets.clavestra import (
    BalanceResponse,
    ClavestraWallet,
    InvoiceCreatedResponse,
    PaymentStatusResponse,
    PayResponseModel,
    _decode_payment_hash,
    _InvoiceStream,
    _map_error,
)

CONTRACT_DIR = Path(__file__).parent / "fixtures" / "clavestra-v15"

OUTBOUND_BOLT11 = (
    "lnbc1u1pjl0uhypp5yxvdqq923atm9ywkpgtu3yxv9w2n44ensrkwfyagvmzqhml2x9gq"
    "dpv2phhwetjv4jzqcneypqyc6t8dp6xu6twva2xjuzzda6qcqzzsxqrrsssp5h3qlnnlf"
    "qekquacwwj9yu7fhujyzxhzqegpxenscw45pgv6xakfq9qyyssqqjruygw0jrcg3365jks"
    "xn6yhsxx7c5pdjrjdlyvuhs7xh8r409h4e3kucc54kgh34pscaq3mg7hn55l8a0qszgzex"
    "80amwrp4gkdgqcpkse88y"
)
OUTBOUND_PAYMENT_HASH = (
    "2198d000aa8f57b291d60a17c890cc2b953ad73380ece493a866c40befea3150"
)


def contract_fixture(name: str) -> dict[str, Any]:
    return json.loads((CONTRACT_DIR / name).read_text(encoding="utf-8"))


class GatewayMock:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.handlers: list[Callable[[httpx.Request], httpx.Response]] = []

    def respond_json(
        self,
        payload: dict[str, Any],
        *,
        status: int = 200,
        content_type: str = "application/json",
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status,
                json=payload,
                headers={"Content-Type": content_type},
                request=request,
            )

        self.handlers.append(handler)

    def respond_fixture(self, name: str, *, status: int = 200) -> None:
        self.respond_json(contract_fixture(name), status=status)

    def timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("response lost", request=request)

        self.handlers.append(handler)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert self.handlers, f"unexpected request: {request.method} {request.url}"
        return self.handlers.pop(0)(request)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def clavestra_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        settings, "clavestra_api_url", "https://gateway.test", raising=False
    )
    monkeypatch.setattr(settings, "clavestra_admin_key", "clv_admin_xxx")
    monkeypatch.setattr(settings, "clavestra_invoice_key", "clv_inv_yyy")
    monkeypatch.setattr(settings, "clavestra_default_currency", "BTC")
    monkeypatch.setattr(settings, "clavestra_verify_tls", True)
    monkeypatch.setattr(settings, "clavestra_timeout_seconds", 30.0)
    monkeypatch.setattr(settings, "lnbits_running", True)


@pytest.fixture
def gateway() -> GatewayMock:
    return GatewayMock()


@pytest.fixture
async def wallet(clavestra_settings, gateway: GatewayMock):
    wallet = ClavestraWallet()
    await wallet.client.aclose()
    wallet.client = httpx.AsyncClient(
        base_url="https://gateway.test",
        transport=httpx.MockTransport(gateway),
        headers={
            "Authorization": "Bearer clv_inv_yyy",
            "Accept": "application/problem+json, application/json",
        },
    )
    try:
        yield wallet
    finally:
        await wallet.cleanup()


@pytest.mark.parametrize(
    ("name", "model", "keys"),
    [
        (
            "status_response_healthy.json",
            BalanceResponse,
            ["error_message", "balance_msat"],
        ),
        (
            "status_response_node_unreachable.json",
            BalanceResponse,
            ["error_message", "balance_msat"],
        ),
        (
            "invoice_response_created.json",
            InvoiceCreatedResponse,
            [
                "ok",
                "checking_id",
                "payment_request",
                "error_message",
                "preimage",
                "fee_msat",
            ],
        ),
        (
            "payment_response_dispatched.json",
            PayResponseModel,
            ["ok", "checking_id", "fee_msat", "preimage", "error_message"],
        ),
        (
            "payment_response_hard_fail.json",
            PayResponseModel,
            ["ok", "checking_id", "fee_msat", "preimage", "error_message"],
        ),
        (
            "payment_response_in_flight.json",
            PayResponseModel,
            ["ok", "checking_id", "fee_msat", "preimage", "error_message"],
        ),
        (
            "payment_status_paid.json",
            PaymentStatusResponse,
            ["paid", "fee_msat", "preimage"],
        ),
        (
            "payment_status_pending.json",
            PaymentStatusResponse,
            ["paid", "fee_msat", "preimage"],
        ),
        (
            "payment_status_unknown_hash.json",
            PaymentStatusResponse,
            ["paid", "fee_msat", "preimage"],
        ),
        (
            "payment_status_with_preimage.json",
            PaymentStatusResponse,
            ["paid", "fee_msat", "preimage"],
        ),
    ],
)
def test_gateway_v15_golden_fixtures(name, model, keys):
    payload = contract_fixture(name)
    assert list(payload) == keys
    model.parse_obj(payload)


def test_missing_settings_raise(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "clavestra_api_url", "")
    monkeypatch.setattr(settings, "clavestra_admin_key", "")
    monkeypatch.setattr(settings, "clavestra_invoice_key", "")
    with pytest.raises(ValueError) as exc:
        ClavestraWallet()
    message = str(exc.value)
    assert "clavestra_api_url" in message
    assert "clavestra_admin_key" in message
    assert "clavestra_invoice_key" in message


def test_map_error_from_problem_type_slug():
    assert _map_error("unauthorized", "bad token") == "unauthorized: bad token"
    assert _map_error("unknown-kind", "boom") == "unknown-kind: boom"


def test_bolt11_payment_hash_is_signed_correlation_key():
    assert _decode_payment_hash(OUTBOUND_BOLT11) == OUTBOUND_PAYMENT_HASH


@pytest.mark.anyio
async def test_status_uses_exact_healthy_fixture(gateway: GatewayMock, wallet):
    gateway.respond_fixture("status_response_healthy.json")
    response = await wallet.status()
    assert response.error_message is None
    assert response.balance_msat == 12345


@pytest.mark.anyio
async def test_status_propagates_node_unreachable_from_http_200(
    gateway: GatewayMock, wallet
):
    gateway.respond_fixture("status_response_node_unreachable.json")
    response = await wallet.status()
    assert response.error_message == "node unreachable"
    assert response.balance_msat == 0


@pytest.mark.anyio
async def test_status_parses_rfc9457_error(gateway: GatewayMock, wallet):
    gateway.respond_json(
        {
            "type": "https://clavestra.com/errors/unauthorized",
            "title": "Unauthorized",
            "status": 401,
            "detail": "authentication required",
        },
        status=401,
        content_type="application/problem+json",
    )
    response = await wallet.status()
    assert response.error_message == "unauthorized: authentication required"


@pytest.mark.anyio
async def test_create_invoice_uses_sats_and_exact_gateway_response(
    gateway: GatewayMock, wallet
):
    payload = contract_fixture("invoice_response_created.json")
    payload.update(
        checking_id=OUTBOUND_PAYMENT_HASH,
        payment_request=OUTBOUND_BOLT11,
    )
    gateway.respond_json(payload)
    response = await wallet.create_invoice(amount=21, memo="coffee")

    assert response.ok is True
    assert response.checking_id == OUTBOUND_PAYMENT_HASH
    assert response.payment_request == OUTBOUND_BOLT11
    assert response.checking_id in wallet.pending_invoices

    request = gateway.requests[0]
    assert request.headers["authorization"] == "Bearer clv_inv_yyy"
    assert json.loads(request.content) == {
        "amount": 21,
        "memo": "coffee",
        "currency": "BTC",
    }


@pytest.mark.anyio
async def test_create_invoice_respects_business_failure_in_http_200(
    gateway: GatewayMock, wallet
):
    payload = contract_fixture("invoice_response_created.json")
    payload.update(
        ok=False,
        checking_id="",
        payment_request="",
        error_message="node unavailable",
    )
    gateway.respond_json(payload)
    response = await wallet.create_invoice(amount=21)
    assert response.ok is False
    assert response.error_message == "node unavailable"
    assert not wallet.pending_invoices


@pytest.mark.anyio
async def test_create_invoice_rejects_mismatched_bolt11_and_checking_id(
    gateway: GatewayMock, wallet
):
    payload = contract_fixture("invoice_response_created.json")
    payload["payment_request"] = OUTBOUND_BOLT11
    gateway.respond_json(payload)
    response = await wallet.create_invoice(amount=21)
    assert response.ok is False
    assert response.error_message == "invalid gateway response"
    assert not wallet.pending_invoices


@pytest.mark.anyio
@pytest.mark.parametrize(
    "advanced_description",
    [
        {"description_hash": b"\x01" * 32},
        {"description_hash": b""},
        {"unhashed_description": b"actual description"},
        {"unhashed_description": b""},
    ],
)
async def test_create_invoice_rejects_gateway_v15_ignored_description_options(
    advanced_description, gateway: GatewayMock, wallet
):
    with pytest.raises(UnsupportedError):
        await wallet.create_invoice(amount=21, **advanced_description)
    assert gateway.requests == []


@pytest.mark.anyio
async def test_create_invoice_parses_rfc9457_validation_error(
    gateway: GatewayMock, wallet
):
    gateway.respond_json(
        {
            "type": "https://clavestra.com/errors/note-validation",
            "title": "Validation failed",
            "status": 400,
            "detail": "currency must be BTC",
        },
        status=400,
        content_type="application/problem+json",
    )
    response = await wallet.create_invoice(amount=21, currency="USD")
    assert response.ok is False
    assert response.error_message == "note-validation: currency must be BTC"


@pytest.mark.anyio
async def test_dispatched_payment_stays_pending_with_bolt11_hash(
    gateway: GatewayMock, wallet
):
    payload = contract_fixture("payment_response_dispatched.json")
    payload["checking_id"] = OUTBOUND_PAYMENT_HASH
    gateway.respond_json(payload)

    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is None
    assert response.checking_id == OUTBOUND_PAYMENT_HASH
    assert response.error_message == "payment dispatched; awaiting settlement"

    request = gateway.requests[0]
    assert request.headers["authorization"] == "Bearer clv_admin_xxx"
    assert json.loads(request.content) == {
        "bolt11": OUTBOUND_BOLT11,
        "fee_limit_msat": 2000,
    }


@pytest.mark.anyio
async def test_settled_payment_requires_matching_hash_and_preimage(
    gateway: GatewayMock, wallet, monkeypatch: pytest.MonkeyPatch
):
    preimage = "cd" * 32
    payment_hash = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()
    monkeypatch.setattr(
        "lnbits.wallets.clavestra._decode_payment_hash", lambda _bolt11: payment_hash
    )
    payload = contract_fixture("payment_response_dispatched.json")
    payload.update(
        checking_id=payment_hash,
        fee_msat=1234,
        preimage=preimage,
    )
    gateway.respond_json(payload)
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is True
    assert response.checking_id == payment_hash
    assert response.fee_msat == 1234
    assert response.preimage == preimage


@pytest.mark.anyio
async def test_well_formed_but_wrong_preimage_stays_pending(
    gateway: GatewayMock, wallet
):
    payload = contract_fixture("payment_response_dispatched.json")
    payload.update(
        checking_id=OUTBOUND_PAYMENT_HASH,
        fee_msat=1234,
        preimage="cd" * 32,
    )
    gateway.respond_json(payload)

    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is None
    assert response.checking_id == OUTBOUND_PAYMENT_HASH
    assert response.preimage is None
    assert response.error_message == "gateway preimage does not match payment hash"


@pytest.mark.anyio
async def test_dispatched_payment_with_empty_preimage_stays_pending(
    gateway: GatewayMock, wallet
):
    payload = contract_fixture("payment_response_dispatched.json")
    payload.update(checking_id=OUTBOUND_PAYMENT_HASH, preimage="")
    gateway.respond_json(payload)
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is None
    assert response.checking_id == OUTBOUND_PAYMENT_HASH


@pytest.mark.anyio
async def test_gateway_in_flight_response_keeps_durable_correlation(
    gateway: GatewayMock, wallet
):
    gateway.respond_fixture("payment_response_in_flight.json")
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is None
    assert response.checking_id == OUTBOUND_PAYMENT_HASH


@pytest.mark.anyio
async def test_authoritative_gateway_hard_fail_is_failed(gateway: GatewayMock, wallet):
    gateway.respond_fixture("payment_response_hard_fail.json")
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is False
    assert response.checking_id == OUTBOUND_PAYMENT_HASH
    assert response.error_message == "invalid bolt11: bad checksum"


@pytest.mark.anyio
async def test_timeout_after_payment_post_is_pending(gateway: GatewayMock, wallet):
    gateway.timeout()
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is None
    assert response.checking_id == OUTBOUND_PAYMENT_HASH
    assert response.error_message == "gateway unreachable"


@pytest.mark.anyio
async def test_malformed_payment_response_is_pending(gateway: GatewayMock, wallet):
    gateway.respond_json({"ok": True})
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is None
    assert response.checking_id == OUTBOUND_PAYMENT_HASH
    assert response.error_message == "invalid gateway response"


@pytest.mark.anyio
async def test_payment_hash_mismatch_is_pending_under_expected_hash(
    gateway: GatewayMock, wallet
):
    payload = contract_fixture("payment_response_dispatched.json")
    gateway.respond_json(payload)
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is None
    assert response.checking_id == OUTBOUND_PAYMENT_HASH
    assert response.error_message == "gateway payment hash mismatch"


@pytest.mark.anyio
@pytest.mark.parametrize(("status", "expected_ok"), [(403, False), (500, None)])
async def test_payment_http_error_distinguishes_pre_dispatch_from_ambiguous(
    status, expected_ok, gateway: GatewayMock, wallet
):
    gateway.respond_json(
        {
            "type": "https://clavestra.com/errors/forbidden",
            "title": "Forbidden",
            "status": status,
            "detail": "payment unavailable",
        },
        status=status,
        content_type="application/problem+json",
    )
    response = await wallet.pay_invoice(OUTBOUND_BOLT11, fee_limit_msat=2000)
    assert response.ok is expected_ok
    assert response.checking_id == OUTBOUND_PAYMENT_HASH


@pytest.mark.anyio
async def test_invalid_bolt11_fails_before_gateway_request(
    gateway: GatewayMock, wallet
):
    response = await wallet.pay_invoice("lnbc1invalid", fee_limit_msat=2000)
    assert response.ok is False
    assert response.checking_id is None
    assert "invalid bolt11" in (response.error_message or "")
    assert gateway.requests == []


@pytest.mark.anyio
async def test_invoice_and_payment_status_use_exact_fixtures(
    gateway: GatewayMock, wallet
):
    gateway.respond_fixture("payment_status_pending.json")
    invoice = await wallet.get_invoice_status("ab" * 32)
    assert invoice.paid is None

    gateway.respond_fixture("payment_status_with_preimage.json")
    payment = await wallet.get_payment_status("ab" * 32)
    assert payment.paid is True
    assert payment.fee_msat == 1234
    assert payment.preimage == "cd" * 32
    assert gateway.requests[-1].headers["authorization"] == "Bearer clv_admin_xxx"


class FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages

    async def recv(self) -> str:
        assert self.messages, "test WebSocket ran out of frames"
        return self.messages.pop(0)


class FakeConnection:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, *_args) -> None:
        return None


@pytest.mark.anyio
async def test_websocket_accepts_plain_hash_without_subscription_frame(
    clavestra_settings, monkeypatch: pytest.MonkeyPatch
):
    payment_hash = "ab" * 32
    websocket = FakeWebSocket(
        [
            '{"type":"invoice_paid","payment_hash":"ignored"}',
            payment_hash,
        ]
    )
    captured: dict[str, Any] = {}

    def connect(url: str, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return FakeConnection(websocket)

    monkeypatch.setattr("lnbits.wallets.clavestra.websockets.connect", connect)
    shutdown = __import__("asyncio").Event()
    stream = _InvoiceStream("https://gateway.test", "clv_inv_yyy", True, shutdown).run()
    assert await anext(stream) == payment_hash
    assert captured["url"] == "wss://gateway.test/v1/ln/invoices/stream"
    assert captured["kwargs"]["additional_headers"] == {
        "Authorization": "Bearer clv_inv_yyy"
    }
    shutdown.set()
    await stream.aclose()


@pytest.mark.anyio
async def test_paid_stream_polls_pending_invoice_when_ws_event_is_missed(
    gateway: GatewayMock,
    wallet,
    monkeypatch: pytest.MonkeyPatch,
):
    checking_id = "ab" * 32
    wallet.pending_invoices.append(checking_id)
    gateway.respond_fixture("payment_status_paid.json")

    async def idle_pump(_queue):
        await wallet._stream_shutdown.wait()

    monkeypatch.setattr(wallet, "_pump_invoice_stream", idle_pump)
    stream = wallet.paid_invoices_stream()
    assert await anext(stream) == checking_id
    assert checking_id not in wallet.pending_invoices
    await stream.aclose()


@pytest.mark.anyio
async def test_paid_stream_uses_ws_hint_and_keeps_polling_as_recovery(
    gateway: GatewayMock,
    wallet,
    monkeypatch: pytest.MonkeyPatch,
):
    checking_id = "ab" * 32
    wallet.pending_invoices.append(checking_id)
    gateway.respond_fixture("payment_status_pending.json")

    async def hint_pump(queue):
        await queue.put(checking_id)
        await wallet._stream_shutdown.wait()

    monkeypatch.setattr(wallet, "_pump_invoice_stream", hint_pump)
    stream = wallet.paid_invoices_stream()
    assert await anext(stream) == checking_id
    assert checking_id not in wallet.pending_invoices
    await stream.aclose()
