"""Clavestra federation wallet backend for LNbits.

Implements `lnbits.wallets.base.Wallet` against a Clavestra gateway
(REST + WebSocket). Configured via three settings — `clavestra_api_url`,
`clavestra_admin_key`, `clavestra_invoice_key` — set in `lnbits/.env`.

Design summary (single-file per LNbits convention):
* HTTP transport: shared `httpx.AsyncClient` with default Bearer
  carrying the invoice key. Only `POST /v1/ln/pay` overrides to the
  admin key per call.
* WS transport: `websockets.connect` to `/v1/ln/invoices/stream`.
  Subscribes once with `{"subscribe":"invoices","since": <int|null>}`,
  yields each `invoice_paid` frame's `payment_hash`, advances the
  `since` cursor on `settled_at`, exponential-backoff reconnect on
  drop. `replay_truncated` frames log WARN and continue.
* Cleanup signals the stream to exit and closes the HTTP client.
* Pydantic v1 models mirror the gateway contract (extra fields
  ignored so gateway-side additions don't break us).
"""

from __future__ import annotations

import asyncio
import json
import ssl
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import websockets
from loguru import logger
from pydantic import BaseModel, Field

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)

log = logger.bind(name="clavestra-wallet")

GATEWAY_UNREACHABLE = "gateway unreachable"

_FALSY = {"0", "false", "no"}

_CODE_MAP: dict[str, str] = {
    "unauthorized": "unauthorized",
    "not_found": "not found",
    "gateway_unreachable": "gateway unreachable",
    "currency_mismatch": "currency mismatch",
    "insufficient_funds": "insufficient funds",
    "invalid_bolt11": "invalid bolt11",
    "payment_failed": "payment failed",
    "internal": "gateway internal error",
}


# ---------------------------------------------------------------------------
# Pydantic models (gateway request/response shapes)
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    class Config:
        extra = "ignore"


class CreateInvoiceRequest(_Base):
    amount_msat: int = Field(..., gt=0)
    memo: str | None = None
    description_hash: str | None = None
    unhashed_description: str | None = None
    expiry: int | None = None
    currency: str | None = None
    idempotency_key: str | None = None


class PayInvoiceRequest(_Base):
    bolt11: str
    fee_limit_msat: int = Field(..., ge=0)


class BalanceResponse(_Base):
    balance_msat: int
    currency: str = "BTC"


class InvoiceCreatedResponse(_Base):
    payment_hash: str
    payment_request: str
    checking_id: str
    expires_at: int


class PayResponseModel(_Base):
    ok: bool | None = None
    payment_hash: str
    checking_id: str
    fee_msat: int | None = None
    preimage: str | None = None
    error_message: str | None = None


class PaymentStatusResponse(_Base):
    paid: bool | None = None
    fee_msat: int | None = None
    preimage: str | None = None


class WSSettlementFrame(_Base):
    type: str
    payment_hash: str
    settled_at: int


class ErrorEnvelope(_Base):
    detail: str
    code: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_error(code: str | None, detail: str | None) -> str:
    prefix = _CODE_MAP.get(code or "")
    detail_str = (detail or "").strip()
    if prefix:
        return f"{prefix}: {detail_str}" if detail_str else prefix
    if detail_str:
        return f"{code}: {detail_str}" if code else detail_str
    return "unknown gateway error"


def _build_invoice_body(
    *,
    amount_msat: int,
    memo: str | None = None,
    description_hash: str | None = None,
    unhashed_description: str | None = None,
    expiry: int | None = None,
    currency: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    req = CreateInvoiceRequest(
        amount_msat=amount_msat,
        memo=memo,
        description_hash=description_hash,
        unhashed_description=unhashed_description,
        expiry=expiry,
        currency=currency,
        idempotency_key=idempotency_key,
    )
    return req.dict(exclude_none=True)


def _build_pay_body(*, bolt11: str, fee_limit_msat: int) -> dict[str, Any]:
    return PayInvoiceRequest(bolt11=bolt11, fee_limit_msat=fee_limit_msat).dict()


def _derive_ws_url(api_url: str) -> str:
    base = api_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    return f"{base}/v1/ln/invoices/stream"


# ---------------------------------------------------------------------------
# WebSocket settlement stream
# ---------------------------------------------------------------------------


class _InvoiceStream:
    def __init__(
        self,
        api_url: str,
        invoice_key: str,
        verify_tls: bool,
        shutdown_event: asyncio.Event,
    ) -> None:
        self._api_url = api_url
        self._invoice_key = invoice_key
        self._verify_tls = verify_tls
        self._shutdown = shutdown_event
        self._last_settled_at: int | None = None
        self._attempt = 0

    def _ssl_ctx(self, url: str) -> ssl.SSLContext | None:
        if not url.startswith("wss://"):
            return None
        if self._verify_tls:
            return None
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def _sleep_or_shutdown(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._shutdown.wait(), timeout=delay)
        except asyncio.TimeoutError:
            return

    async def run(self) -> AsyncGenerator[str, None]:  # noqa: C901
        url = _derive_ws_url(self._api_url)
        headers = {"Authorization": f"Bearer {self._invoice_key}"}
        ssl_ctx = self._ssl_ctx(url)

        while not self._shutdown.is_set():
            try:
                connect_kwargs: dict[str, Any] = {
                    "additional_headers": headers,
                    "ping_interval": 20,
                    "ping_timeout": 20,
                }
                if ssl_ctx is not None:
                    connect_kwargs["ssl"] = ssl_ctx
                async with websockets.connect(url, **connect_kwargs) as ws:
                    sub = {
                        "subscribe": "invoices",
                        "since": self._last_settled_at,
                    }
                    await ws.send(json.dumps(sub))
                    log.debug("ws subscribed since={}", self._last_settled_at)

                    while not self._shutdown.is_set():
                        recv_task = asyncio.create_task(ws.recv())
                        shutdown_task = asyncio.create_task(self._shutdown.wait())
                        done, _pending = await asyncio.wait(
                            {recv_task, shutdown_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if shutdown_task in done:
                            recv_task.cancel()
                            try:
                                await recv_task
                            except (asyncio.CancelledError, Exception) as e:
                                log.debug("recv_task cancel completed: {}", e)
                            return
                        shutdown_task.cancel()
                        try:
                            await shutdown_task
                        except (asyncio.CancelledError, Exception) as e:
                            log.debug("shutdown_task cancel completed: {}", e)

                        raw = recv_task.result()
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError as e:
                            log.warning("ws bad json: {}", e)
                            break

                        mtype = msg.get("type")
                        if mtype == "invoice_paid":
                            try:
                                frame = WSSettlementFrame(**msg)
                            except Exception as e:
                                log.warning("ws settlement parse failed: {}", e)
                                continue
                            self._last_settled_at = max(
                                self._last_settled_at or 0, frame.settled_at
                            )
                            self._attempt = 0
                            yield frame.payment_hash
                        elif mtype == "replay_truncated":
                            log.warning(
                                "ws replay_truncated: oldest_available={}",
                                msg.get("oldest_available"),
                            )
                            continue
                        elif mtype == "error":
                            log.warning("ws error frame: {}", msg)
                            break
                        elif mtype == "ping":
                            continue
                        else:
                            log.debug("ws unknown frame type: {}", mtype)
                            continue
            except (
                websockets.ConnectionClosed,
                websockets.InvalidStatus,
                websockets.InvalidHandshake,
                OSError,
                asyncio.TimeoutError,
                json.JSONDecodeError,
            ) as e:
                log.warning("ws disconnect: {}", e)

            if self._shutdown.is_set():
                return
            delay = min(2**self._attempt, 60)
            self._attempt += 1
            log.debug("ws backoff sleep={}s attempt={}", delay, self._attempt)
            await self._sleep_or_shutdown(delay)


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------


class ClavestraWallet(Wallet):
    """Clavestra federation gateway backend.

    Reads three required settings — `clavestra_api_url`,
    `clavestra_admin_key`, `clavestra_invoice_key` — and fails fast
    listing every missing name.
    """

    def __init__(self) -> None:
        super().__init__()

        missing: list[str] = []
        api_url = (settings.clavestra_api_url or "").strip()
        admin_key = (settings.clavestra_admin_key or "").strip()
        invoice_key = (settings.clavestra_invoice_key or "").strip()
        if not api_url:
            missing.append("clavestra_api_url")
        if not admin_key:
            missing.append("clavestra_admin_key")
        if not invoice_key:
            missing.append("clavestra_invoice_key")
        if missing:
            raise ValueError(
                f"cannot initialize ClavestraWallet: missing {sorted(missing)}"
            )

        self._api_url = api_url
        self._admin_key = admin_key
        self._invoice_key = invoice_key
        self._timeout_seconds = float(settings.clavestra_timeout_seconds or 30.0)
        verify_raw = settings.clavestra_verify_tls
        if verify_raw is None or verify_raw == "":
            self._verify_tls = True
        elif isinstance(verify_raw, bool):
            self._verify_tls = verify_raw
        else:
            self._verify_tls = str(verify_raw).strip().lower() not in _FALSY
        self._default_currency = (
            settings.clavestra_default_currency or "BTC"
        ).strip() or "BTC"

        self.client = httpx.AsyncClient(
            base_url=self._api_url,
            timeout=self._timeout_seconds,
            verify=self._verify_tls,
            headers={"Authorization": f"Bearer {self._invoice_key}"},
        )
        self._stream_shutdown = asyncio.Event()
        log.debug("ClavestraWallet initialized api_url={}", self._api_url)

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._admin_key}"}

    async def cleanup(self) -> None:
        log.debug("ClavestraWallet cleanup — signaling stream shutdown")
        self._stream_shutdown.set()
        try:
            await self.client.aclose()
        except RuntimeError as e:
            log.warning("Error closing clavestra client: {}", e)

    async def status(self) -> StatusResponse:
        try:
            resp = await self.client.get("/v1/wallet/balance")
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.warning("status network error: {}", e)
            return StatusResponse(error_message=GATEWAY_UNREACHABLE, balance_msat=0)

        if resp.is_success:
            try:
                parsed = BalanceResponse(**resp.json())
            except Exception as e:
                log.warning("status parse failed: {}", e)
                return StatusResponse(
                    error_message="invalid gateway response", balance_msat=0
                )
            return StatusResponse(error_message=None, balance_msat=parsed.balance_msat)

        try:
            envelope = ErrorEnvelope(**resp.json())
            msg = _map_error(envelope.code, envelope.detail)
        except Exception:
            msg = f"http {resp.status_code}"
        return StatusResponse(error_message=msg, balance_msat=0)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs: Any,
    ) -> InvoiceResponse:
        currency = kwargs.get("currency") or self._default_currency
        body = _build_invoice_body(
            amount_msat=amount * 1000,
            memo=memo,
            description_hash=description_hash.hex() if description_hash else None,
            unhashed_description=(
                unhashed_description.decode() if unhashed_description else None
            ),
            expiry=kwargs.get("expiry"),
            currency=currency,
            idempotency_key=kwargs.get("idempotency_key"),
        )
        try:
            resp = await self.client.post("/v1/ln/invoice", json=body)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.warning("create_invoice network error: {}", e)
            return InvoiceResponse(ok=False, error_message=GATEWAY_UNREACHABLE)

        if resp.is_success:
            try:
                parsed = InvoiceCreatedResponse(**resp.json())
            except Exception as e:
                log.warning("create_invoice parse failed: {}", e)
                return InvoiceResponse(
                    ok=False, error_message="invalid gateway response"
                )
            return InvoiceResponse(
                ok=True,
                checking_id=parsed.payment_hash,
                payment_request=parsed.payment_request,
                error_message=None,
            )

        try:
            envelope = ErrorEnvelope(**resp.json())
            code, detail = envelope.code, envelope.detail
        except Exception:
            code, detail = None, resp.text
        return InvoiceResponse(ok=False, error_message=_map_error(code, detail))

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        body = _build_pay_body(bolt11=bolt11, fee_limit_msat=fee_limit_msat)
        try:
            resp = await self.client.post(
                "/v1/ln/pay", json=body, headers=self._admin_headers()
            )
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.warning("pay_invoice network error: {}", e)
            return PaymentResponse(ok=False, error_message=GATEWAY_UNREACHABLE)

        if resp.is_success:
            try:
                parsed = PayResponseModel(**resp.json())
            except Exception as e:
                log.warning("pay_invoice parse failed: {}", e)
                return PaymentResponse(
                    ok=False, error_message="invalid gateway response"
                )
            return PaymentResponse(
                ok=parsed.ok,
                checking_id=parsed.checking_id or parsed.payment_hash,
                fee_msat=parsed.fee_msat,
                preimage=parsed.preimage,
                error_message=parsed.error_message,
            )

        try:
            envelope = ErrorEnvelope(**resp.json())
            code, detail = envelope.code, envelope.detail
        except Exception:
            code, detail = None, resp.text
        return PaymentResponse(ok=False, error_message=_map_error(code, detail))

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            resp = await self.client.get(f"/v1/ln/invoice/{checking_id}")
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.warning("get_invoice_status network error: {}", e)
            return PaymentStatus(paid=None)

        if resp.status_code == 404:
            return PaymentStatus(paid=None)
        if resp.is_success:
            try:
                parsed = PaymentStatusResponse(**resp.json())
            except Exception as e:
                log.warning("get_invoice_status parse failed: {}", e)
                return PaymentStatus(paid=None)
            return PaymentStatus(
                paid=parsed.paid, fee_msat=parsed.fee_msat, preimage=parsed.preimage
            )
        log.warning(
            "get_invoice_status http {} body={}", resp.status_code, resp.text[:200]
        )
        return PaymentStatus(paid=None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            resp = await self.client.get(
                f"/v1/ln/payment/{checking_id}", headers=self._admin_headers()
            )
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.warning("get_payment_status network error: {}", e)
            return PaymentStatus(paid=None)

        if resp.status_code == 404:
            return PaymentStatus(paid=None)
        if resp.is_success:
            try:
                parsed = PaymentStatusResponse(**resp.json())
            except Exception as e:
                log.warning("get_payment_status parse failed: {}", e)
                return PaymentStatus(paid=None)
            return PaymentStatus(
                paid=parsed.paid, fee_msat=parsed.fee_msat, preimage=parsed.preimage
            )
        log.warning(
            "get_payment_status http {} body={}", resp.status_code, resp.text[:200]
        )
        return PaymentStatus(paid=None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self._stream_shutdown.clear()
        stream = _InvoiceStream(
            self._api_url,
            self._invoice_key,
            self._verify_tls,
            self._stream_shutdown,
        )
        async for payment_hash in stream.run():
            yield payment_hash
