"""Clavestra federation gateway funding source for LNbits.

The REST models in this module mirror the gateway v15 wire contract. Outbound
payments are correlated with the payment hash signed into the submitted BOLT11;
transport or response ambiguity is therefore kept pending and can be reconciled
through the gateway's payment-status endpoint.

The gateway invoice WebSocket is an at-most-once stream of plain, lowercase
64-character payment hashes. It is used as a low-latency hint only. Invoices
created by this process are also polled so a dropped WebSocket frame cannot
strand an incoming payment.
"""

from __future__ import annotations

import asyncio
import re
import ssl
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any

import httpx
import websockets
from bolt11 import decode as bolt11_decode
from loguru import logger
from pydantic import BaseModel, Field

from lnbits.exceptions import UnsupportedError
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
INVALID_GATEWAY_RESPONSE = "invalid gateway response"

_FALSY = {"0", "false", "no"}
_PAYMENT_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_POLL_INTERVAL_SECONDS = 5.0

# These responses are produced before the gateway can dispatch a payment. All
# other HTTP failures after POST /v1/ln/pay are conservatively treated as
# ambiguous and reconciled by the BOLT11-derived payment hash.
_PRE_DISPATCH_HTTP_FAILURES = {400, 401, 403, 404, 405, 415, 422}

_CODE_MAP: dict[str, str] = {
    "unauthorized": "unauthorized",
    "forbidden": "forbidden",
    "not-found": "not found",
    "not_found": "not found",
    "gateway-unreachable": "gateway unreachable",
    "gateway_unreachable": "gateway unreachable",
    "currency-mismatch": "currency mismatch",
    "currency_mismatch": "currency mismatch",
    "insufficient-funds": "insufficient funds",
    "insufficient_funds": "insufficient funds",
    "invalid-bolt11": "invalid bolt11",
    "invalid_bolt11": "invalid bolt11",
    "payment-failed": "payment failed",
    "payment_failed": "payment failed",
    "internal": "gateway internal error",
}


# ---------------------------------------------------------------------------
# Gateway v15 wire models
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    class Config:
        # Additive gateway fields must not break an otherwise compatible LNbits
        # client. Every v15 field below is still required explicitly.
        extra = "ignore"


class CreateInvoiceRequest(_Base):
    amount: int = Field(..., gt=0)
    memo: str | None = None
    expiry: int | None = Field(default=None, gt=0)
    currency: str = "BTC"


class PayInvoiceRequest(_Base):
    bolt11: str
    fee_limit_msat: int | None = Field(default=None, ge=0)


class BalanceResponse(_Base):
    error_message: str | None = Field(...)
    balance_msat: int = Field(..., ge=0)


class InvoiceCreatedResponse(_Base):
    ok: bool
    checking_id: str
    payment_request: str
    error_message: str | None = Field(...)
    preimage: str | None = Field(...)
    fee_msat: int | None = Field(..., ge=0)


class PayResponseModel(_Base):
    ok: bool | None = Field(...)
    checking_id: str | None = Field(...)
    fee_msat: int | None = Field(..., ge=0)
    preimage: str | None = Field(...)
    error_message: str | None = Field(...)


class PaymentStatusResponse(_Base):
    paid: bool | None = Field(...)
    fee_msat: int | None = Field(..., ge=0)
    preimage: str | None = Field(...)


class ProblemDetails(_Base):
    """RFC 9457 error body returned by the gateway for non-business errors."""

    type_uri: str = Field(..., alias="type")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


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


def _problem_code(type_uri: str) -> str:
    return type_uri.rstrip("/").rsplit("/", 1)[-1]


def _response_error(response: httpx.Response) -> str:
    try:
        problem = ProblemDetails.parse_obj(response.json())
    except Exception as exc:
        log.warning(
            "RFC 9457 response parse failed status={} error={}",
            response.status_code,
            exc,
        )
        return f"gateway http {response.status_code}"

    if problem.status != response.status_code:
        log.warning(
            "RFC 9457 status mismatch body={} http={}",
            problem.status,
            response.status_code,
        )
    return _map_error(_problem_code(problem.type_uri), problem.detail or problem.title)


def _build_invoice_body(
    *,
    amount: int,
    memo: str | None = None,
    expiry: int | None = None,
    currency: str = "BTC",
) -> dict[str, Any]:
    request = CreateInvoiceRequest(
        amount=amount,
        memo=memo,
        expiry=expiry,
        currency=currency,
    )
    return request.dict(exclude_none=True)


def _build_pay_body(*, bolt11: str, fee_limit_msat: int) -> dict[str, Any]:
    return PayInvoiceRequest(bolt11=bolt11, fee_limit_msat=fee_limit_msat).dict(
        exclude_none=True
    )


def _derive_ws_url(api_url: str) -> str:
    base = api_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    return f"{base}/v1/ln/invoices/stream"


def _is_payment_hash(value: str | None) -> bool:
    return bool(value and _PAYMENT_HASH_RE.fullmatch(value))


def _decode_payment_hash(bolt11: str) -> str:
    invoice = bolt11_decode(bolt11.strip())
    payment_hash = str(invoice.payment_hash).lower()
    if not _is_payment_hash(payment_hash):
        raise ValueError("BOLT11 does not contain a valid payment hash")
    return payment_hash


def _pending_payment(payment_hash: str, error_message: str) -> PaymentResponse:
    return PaymentResponse(
        ok=None,
        checking_id=payment_hash,
        error_message=error_message,
    )


# ---------------------------------------------------------------------------
# WebSocket settlement hint stream
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
        self._attempt = 0

    def _ssl_ctx(self, url: str) -> ssl.SSLContext | None:
        if not url.startswith("wss://") or self._verify_tls:
            return None
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def _sleep_or_shutdown(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._shutdown.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    async def run(self) -> AsyncGenerator[str, None]:
        url = _derive_ws_url(self._api_url)
        headers = {"Authorization": f"Bearer {self._invoice_key}"}
        ssl_ctx = self._ssl_ctx(url)

        while not self._shutdown.is_set() and settings.lnbits_running:
            try:
                connect_kwargs: dict[str, Any] = {
                    "additional_headers": headers,
                    "ping_interval": 20,
                    "ping_timeout": 20,
                }
                if ssl_ctx is not None:
                    connect_kwargs["ssl"] = ssl_ctx

                async with websockets.connect(url, **connect_kwargs) as ws:
                    self._attempt = 0
                    log.debug("connected to Clavestra invoice stream")
                    while not self._shutdown.is_set() and settings.lnbits_running:
                        recv_task = asyncio.create_task(ws.recv())
                        shutdown_task = asyncio.create_task(self._shutdown.wait())
                        done, _ = await asyncio.wait(
                            {recv_task, shutdown_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if shutdown_task in done:
                            recv_task.cancel()
                            with suppress(asyncio.CancelledError):
                                await recv_task
                            return

                        shutdown_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await shutdown_task

                        raw = recv_task.result()
                        if not isinstance(raw, str) or not _is_payment_hash(raw):
                            log.warning("ignoring invalid Clavestra WS frame")
                            continue
                        yield raw
            except asyncio.CancelledError:
                raise
            except (
                websockets.ConnectionClosed,
                websockets.InvalidStatus,
                websockets.InvalidHandshake,
                OSError,
                asyncio.TimeoutError,
            ) as exc:
                log.warning("Clavestra invoice stream disconnected: {}", exc)

            if self._shutdown.is_set() or not settings.lnbits_running:
                return
            delay = min(2**self._attempt, 60)
            self._attempt += 1
            await self._sleep_or_shutdown(delay)


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------


class ClavestraWallet(Wallet):
    """LNbits funding source backed by a Clavestra federation gateway."""

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
            headers={
                "Authorization": f"Bearer {self._invoice_key}",
                "Accept": "application/problem+json, application/json",
            },
        )
        self._stream_shutdown = asyncio.Event()

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._admin_key}"}

    def _remove_pending_invoice(self, checking_id: str) -> None:
        while checking_id in self.pending_invoices:
            self.pending_invoices.remove(checking_id)

    async def cleanup(self) -> None:
        self._stream_shutdown.set()
        try:
            await self.client.aclose()
        except RuntimeError as exc:
            log.warning("error closing Clavestra client: {}", exc)

    async def status(self) -> StatusResponse:
        try:
            response = await self.client.get("/v1/wallet/balance")
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            log.warning("Clavestra status network error: {}", exc)
            return StatusResponse(GATEWAY_UNREACHABLE, 0)

        if not response.is_success:
            return StatusResponse(_response_error(response), 0)

        try:
            parsed = BalanceResponse.parse_obj(response.json())
        except Exception as exc:
            log.warning("Clavestra status parse failed: {}", exc)
            return StatusResponse(INVALID_GATEWAY_RESPONSE, 0)
        return StatusResponse(parsed.error_message, parsed.balance_msat)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs: Any,
    ) -> InvoiceResponse:
        # Gateway v15 accepts these fields in JSON but does not pass either to
        # the Lightning node. Silently accepting them would mint an invoice
        # with different BOLT11 semantics than LNbits requested.
        if description_hash is not None or unhashed_description is not None:
            raise UnsupportedError(
                "description_hash and unhashed_description are not supported "
                "by Clavestra gateway v15"
            )

        try:
            body = _build_invoice_body(
                amount=amount,
                memo=memo,
                expiry=kwargs.get("expiry"),
                currency=kwargs.get("currency") or self._default_currency,
            )
        except ValueError as exc:
            return InvoiceResponse(ok=False, error_message=str(exc))

        try:
            response = await self.client.post("/v1/ln/invoice", json=body)
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            log.warning("Clavestra create_invoice network error: {}", exc)
            return InvoiceResponse(ok=False, error_message=GATEWAY_UNREACHABLE)

        if not response.is_success:
            return InvoiceResponse(ok=False, error_message=_response_error(response))

        try:
            parsed = InvoiceCreatedResponse.parse_obj(response.json())
        except Exception as exc:
            log.warning("Clavestra create_invoice parse failed: {}", exc)
            return InvoiceResponse(ok=False, error_message=INVALID_GATEWAY_RESPONSE)

        if not parsed.ok:
            return InvoiceResponse(
                ok=False,
                error_message=parsed.error_message or "gateway invoice creation failed",
            )
        try:
            invoice_payment_hash = _decode_payment_hash(parsed.payment_request)
        except Exception as exc:
            log.warning("Clavestra invoice BOLT11 decode failed: {}", exc)
            return InvoiceResponse(ok=False, error_message=INVALID_GATEWAY_RESPONSE)
        if parsed.checking_id != invoice_payment_hash:
            log.warning(
                "Clavestra invoice hash mismatch checking_id={} bolt11_hash={}",
                parsed.checking_id,
                invoice_payment_hash,
            )
            return InvoiceResponse(ok=False, error_message=INVALID_GATEWAY_RESPONSE)

        if parsed.checking_id not in self.pending_invoices:
            self.pending_invoices.append(parsed.checking_id)
        return InvoiceResponse(
            ok=True,
            checking_id=parsed.checking_id,
            payment_request=parsed.payment_request,
            preimage=parsed.preimage,
            fee_msat=parsed.fee_msat,
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        # Decode before performing the side effect. The hash signed into the
        # invoice is LNbits' durable correlation key for every response path.
        try:
            payment_hash = _decode_payment_hash(bolt11)
            body = _build_pay_body(
                bolt11=bolt11,
                fee_limit_msat=fee_limit_msat,
            )
        except Exception as exc:
            return PaymentResponse(ok=False, error_message=f"invalid bolt11: {exc}")

        try:
            response = await self.client.post(
                "/v1/ln/pay", json=body, headers=self._admin_headers()
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            log.warning("Clavestra pay_invoice ambiguous network error: {}", exc)
            return _pending_payment(payment_hash, GATEWAY_UNREACHABLE)

        if not response.is_success:
            error_message = _response_error(response)
            if response.status_code in _PRE_DISPATCH_HTTP_FAILURES:
                return PaymentResponse(
                    ok=False,
                    checking_id=payment_hash,
                    error_message=error_message,
                )
            return _pending_payment(payment_hash, error_message)

        try:
            parsed = PayResponseModel.parse_obj(response.json())
        except Exception as exc:
            log.warning("Clavestra pay_invoice ambiguous parse failure: {}", exc)
            return _pending_payment(payment_hash, INVALID_GATEWAY_RESPONSE)

        if parsed.ok is False:
            return PaymentResponse(
                ok=False,
                checking_id=payment_hash,
                error_message=parsed.error_message or "gateway payment failed",
            )

        if parsed.checking_id is not None and parsed.checking_id != payment_hash:
            log.error(
                "Clavestra payment hash mismatch expected={} returned={}",
                payment_hash,
                parsed.checking_id,
            )
            return _pending_payment(payment_hash, "gateway payment hash mismatch")

        if parsed.ok is None or parsed.checking_id is None:
            return _pending_payment(
                payment_hash,
                parsed.error_message or "gateway payment state unknown",
            )

        # Gateway ok=true means dispatched. Only a well-formed preimage is
        # terminal settlement evidence; otherwise keep LNbits pending and
        # reconcile by hash.
        settled = _is_payment_hash(parsed.preimage)
        return PaymentResponse(
            ok=True if settled else None,
            checking_id=payment_hash,
            fee_msat=parsed.fee_msat,
            preimage=parsed.preimage,
            error_message=(
                parsed.error_message
                if settled
                else parsed.error_message or "payment dispatched; awaiting settlement"
            ),
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            response = await self.client.get(f"/v1/ln/invoice/{checking_id}")
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            log.warning("Clavestra invoice status network error: {}", exc)
            return PaymentStatus(paid=None)

        if not response.is_success:
            log.warning(
                "Clavestra invoice status failed: {}",
                _response_error(response),
            )
            return PaymentStatus(paid=None)
        try:
            parsed = PaymentStatusResponse.parse_obj(response.json())
        except Exception as exc:
            log.warning("Clavestra invoice status parse failed: {}", exc)
            return PaymentStatus(paid=None)
        return PaymentStatus(
            paid=parsed.paid,
            fee_msat=parsed.fee_msat,
            preimage=parsed.preimage,
        )

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            response = await self.client.get(
                f"/v1/ln/payment/{checking_id}",
                headers=self._admin_headers(),
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            log.warning("Clavestra payment status network error: {}", exc)
            return PaymentStatus(paid=None)

        if not response.is_success:
            log.warning(
                "Clavestra payment status failed: {}",
                _response_error(response),
            )
            return PaymentStatus(paid=None)
        try:
            parsed = PaymentStatusResponse.parse_obj(response.json())
        except Exception as exc:
            log.warning("Clavestra payment status parse failed: {}", exc)
            return PaymentStatus(paid=None)
        return PaymentStatus(
            paid=parsed.paid,
            fee_msat=parsed.fee_msat,
            preimage=parsed.preimage,
        )

    async def _reconcile_pending_invoices(self) -> list[str]:
        settled: list[str] = []
        for checking_id in list(dict.fromkeys(self.pending_invoices)):
            try:
                status = await self.get_invoice_status(checking_id)
            except Exception as exc:
                log.warning(
                    "could not reconcile Clavestra invoice {}: {}",
                    checking_id,
                    exc,
                )
                continue
            if status.success:
                self._remove_pending_invoice(checking_id)
                settled.append(checking_id)
            elif status.failed:
                self._remove_pending_invoice(checking_id)
        return settled

    async def _pump_invoice_stream(self, queue: asyncio.Queue[str]) -> None:
        stream = _InvoiceStream(
            self._api_url,
            self._invoice_key,
            self._verify_tls,
            self._stream_shutdown,
        )
        async for payment_hash in stream.run():
            await queue.put(payment_hash)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self._stream_shutdown.clear()
        queue: asyncio.Queue[str] = asyncio.Queue()
        ws_task = asyncio.create_task(self._pump_invoice_stream(queue))
        loop = asyncio.get_running_loop()
        next_poll = loop.time()

        try:
            while settings.lnbits_running and not self._stream_shutdown.is_set():
                now = loop.time()
                if now >= next_poll:
                    for checking_id in await self._reconcile_pending_invoices():
                        yield checking_id
                    next_poll = loop.time() + _POLL_INTERVAL_SECONDS
                    continue

                try:
                    checking_id = await asyncio.wait_for(
                        queue.get(), timeout=max(0.0, next_poll - now)
                    )
                except asyncio.TimeoutError:
                    continue

                self._remove_pending_invoice(checking_id)
                yield checking_id
        finally:
            self._stream_shutdown.set()
            ws_task.cancel()
            with suppress(asyncio.CancelledError):
                await ws_task
