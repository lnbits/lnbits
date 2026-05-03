"""Unit tests for the Clavestra wallet backend.

Covers configuration validation, the five REST methods, and the gateway
error envelope mapping. The WebSocket settlement stream
(`paid_invoices_stream`) is exercised against a live gateway in
integration testing — its in-process simulation is too heavy for the
unit-test surface and the contract is straightforward
(JSON-frame in / `payment_hash` out, with reconnect-with-since on drop).

Tests use `pytest-httpserver` (already in the LNbits dev deps) to
serve the gateway, and `monkeypatch` to set the `clavestra_*`
settings — no env vars, no real network.
"""

from __future__ import annotations

import pytest
from pytest_httpserver import HTTPServer

from lnbits.settings import settings
from lnbits.wallets.clavestra import ClavestraWallet, _map_error


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8556)


@pytest.fixture
def gateway_url(httpserver: HTTPServer) -> str:
    return httpserver.url_for("").rstrip("/")


@pytest.fixture
def clavestra_settings(monkeypatch, gateway_url):
    monkeypatch.setattr(settings, "clavestra_api_url", gateway_url, raising=False)
    monkeypatch.setattr(settings, "clavestra_admin_key", "clv_admin_xxx", raising=False)
    monkeypatch.setattr(settings, "clavestra_invoice_key", "clv_inv_yyy", raising=False)
    monkeypatch.setattr(settings, "clavestra_default_currency", "BTC", raising=False)


@pytest.fixture
async def wallet(clavestra_settings):
    w = ClavestraWallet()
    try:
        yield w
    finally:
        await w.cleanup()


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --- Construction / config ----------------------------------------------------


def test_missing_settings_raise(monkeypatch):
    monkeypatch.setattr(settings, "clavestra_api_url", "", raising=False)
    monkeypatch.setattr(settings, "clavestra_admin_key", "", raising=False)
    monkeypatch.setattr(settings, "clavestra_invoice_key", "", raising=False)
    with pytest.raises(ValueError) as exc:
        ClavestraWallet()
    msg = str(exc.value)
    assert "clavestra_api_url" in msg
    assert "clavestra_admin_key" in msg
    assert "clavestra_invoice_key" in msg


def test_missing_only_one_listed(monkeypatch):
    monkeypatch.setattr(settings, "clavestra_api_url", "http://x", raising=False)
    monkeypatch.setattr(settings, "clavestra_admin_key", "a", raising=False)
    monkeypatch.setattr(settings, "clavestra_invoice_key", "", raising=False)
    with pytest.raises(ValueError) as exc:
        ClavestraWallet()
    assert "clavestra_invoice_key" in str(exc.value)
    assert "clavestra_api_url" not in str(exc.value)


# --- Error mapping ------------------------------------------------------------


def test_map_error_known_code():
    assert _map_error("unauthorized", "bad token") == "unauthorized: bad token"


def test_map_error_known_code_no_detail():
    assert _map_error("not_found", "") == "not found"


def test_map_error_unknown_code_with_detail():
    assert _map_error("weird", "boom") == "weird: boom"


def test_map_error_empty_everything():
    assert _map_error(None, None) == "unknown gateway error"


# --- status -------------------------------------------------------------------


@pytest.mark.anyio
async def test_status_ok(httpserver: HTTPServer, wallet):
    httpserver.expect_request("/v1/wallet/balance", method="GET").respond_with_json(
        {"balance_msat": 12345, "currency": "BTC"}
    )
    r = await wallet.status()
    assert r.balance_msat == 12345
    assert r.error_message is None


@pytest.mark.anyio
async def test_status_error_envelope(httpserver: HTTPServer, wallet):
    httpserver.expect_request("/v1/wallet/balance", method="GET").respond_with_json(
        {"detail": "nope", "code": "unauthorized"}, status=401
    )
    r = await wallet.status()
    assert "unauthorized" in (r.error_message or "")
    assert r.balance_msat == 0


# --- create_invoice -----------------------------------------------------------


@pytest.mark.anyio
async def test_create_invoice_ok(httpserver: HTTPServer, wallet):
    httpserver.expect_request("/v1/ln/invoice", method="POST").respond_with_json(
        {
            "payment_hash": "h" * 64,
            "payment_request": "lnbc1test",
            "checking_id": "h" * 64,
            "expires_at": 1234567890,
        }
    )
    r = await wallet.create_invoice(amount=21, memo="hi")
    assert r.ok is True
    assert r.payment_request == "lnbc1test"
    assert r.checking_id == "h" * 64


@pytest.mark.anyio
async def test_create_invoice_currency_mismatch(httpserver: HTTPServer, wallet):
    httpserver.expect_request("/v1/ln/invoice", method="POST").respond_with_json(
        {"detail": "wallet is USD", "code": "currency_mismatch"}, status=422
    )
    r = await wallet.create_invoice(amount=21)
    assert r.ok is False
    assert "currency mismatch" in (r.error_message or "")


# --- pay_invoice --------------------------------------------------------------


@pytest.mark.anyio
async def test_pay_invoice_ok_uses_admin_key(httpserver: HTTPServer, wallet):
    httpserver.expect_request(
        "/v1/ln/pay",
        method="POST",
        headers={"Authorization": "Bearer clv_admin_xxx"},
    ).respond_with_json(
        {
            "ok": True,
            "payment_hash": "p" * 64,
            "checking_id": "p" * 64,
            "fee_msat": 1000,
            "preimage": "0" * 64,
        }
    )
    r = await wallet.pay_invoice("lnbc1test", fee_limit_msat=2000)
    assert r.ok is True
    assert r.fee_msat == 1000


@pytest.mark.anyio
async def test_pay_invoice_failed(httpserver: HTTPServer, wallet):
    httpserver.expect_request(
        "/v1/ln/pay",
        method="POST",
        headers={"Authorization": "Bearer clv_admin_xxx"},
    ).respond_with_json({"detail": "no route", "code": "payment_failed"}, status=502)
    r = await wallet.pay_invoice("lnbc1test", fee_limit_msat=2000)
    assert r.ok is False
    assert "payment failed" in (r.error_message or "")


# --- get_invoice_status -------------------------------------------------------


@pytest.mark.anyio
async def test_get_invoice_status_paid(httpserver: HTTPServer, wallet):
    httpserver.expect_request("/v1/ln/invoice/abc", method="GET").respond_with_json(
        {"paid": True, "fee_msat": 0, "preimage": "0" * 64}
    )
    r = await wallet.get_invoice_status("abc")
    assert r.paid is True


@pytest.mark.anyio
async def test_get_invoice_status_404(httpserver: HTTPServer, wallet):
    httpserver.expect_request("/v1/ln/invoice/abc", method="GET").respond_with_data(
        "", status=404
    )
    r = await wallet.get_invoice_status("abc")
    assert r.paid is None


# --- get_payment_status -------------------------------------------------------


@pytest.mark.anyio
async def test_get_payment_status_uses_admin(httpserver: HTTPServer, wallet):
    httpserver.expect_request(
        "/v1/ln/payment/p",
        method="GET",
        headers={"Authorization": "Bearer clv_admin_xxx"},
    ).respond_with_json({"paid": True, "fee_msat": 5, "preimage": "0" * 64})
    r = await wallet.get_payment_status("p")
    assert r.paid is True
    assert r.fee_msat == 5
