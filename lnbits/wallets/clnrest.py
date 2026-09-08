import asyncio
import base64
import json
import os
import ssl
import uuid
from collections.abc import AsyncGenerator
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse

import httpx
from bolt11 import Bolt11Exception
from bolt11.decode import decode
from loguru import logger

from lnbits.exceptions import UnsupportedError
from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash, verify_preimage

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)


class CLNRestWallet(Wallet):
    """
    Core Lightning REST wallet backend.

    This implementation addresses:

    - Core Lightning msat response compatibility
    - description-hash invoices
    - preimage verification
    - correct waitanyinvoice semantics
    - listener bootstrap to prevent historical payment replay
    - payment reconciliation/idempotency
    - ambiguous "already paid" responses
    - improved CLN REST error reporting
    - safer TLS handling
    - current Core Lightning pay/renepay behavior

    LNbits internal payments are handled by LNbits core before pay_invoice()
    reaches the funding source.
    """

    def __init__(self):
        super().__init__()

        if not settings.clnrest_url:
            raise ValueError("Cannot initialize CLNRestWallet: missing CLNREST_URL")

        if not settings.clnrest_readonly_rune:
            raise ValueError(
                "Cannot initialize CLNRestWallet: missing CLNREST_READONLY_RUNE"
            )

        self.url = normalize_endpoint(settings.clnrest_url)

        if not settings.clnrest_nodeid:
            logger.info(
                "missing CLNREST_NODEID, but this is only needed for CLN v23.08"
            )

        self.base_headers = {
            "accept": "application/json",
            "User-Agent": settings.user_agent,
            "Content-Type": "application/json",
        }

        if settings.clnrest_nodeid is not None:
            self.base_headers["nodeid"] = settings.clnrest_nodeid

        self.readonly_headers = {
            **self.base_headers,
            "rune": settings.clnrest_readonly_rune,
        }

        self.invoice_headers = (
            {
                **self.base_headers,
                "rune": settings.clnrest_invoice_rune,
            }
            if settings.clnrest_invoice_rune
            else None
        )

        self.pay_headers = (
            {
                **self.base_headers,
                "rune": settings.clnrest_pay_rune,
            }
            if settings.clnrest_pay_rune
            else None
        )

        self.renepay_headers = (
            {
                **self.base_headers,
                "rune": settings.clnrest_renepay_rune,
            }
            if settings.clnrest_renepay_rune
            else None
        )

        if not self.invoice_headers:
            logger.warning(
                "Will be unable to create invoices without "
                "setting CLNREST_INVOICE_RUNE"
            )

        if not self.pay_headers:
            logger.warning(
                "CLNREST_PAY_RUNE is not configured. "
                "Will use renepay only if CLNREST_RENEPAY_RUNE is configured."
            )

        if self.renepay_headers:
            logger.warning(
                "CLNREST_RENEPAY_RUNE is configured. Core Lightning renepay "
                "is deprecated; pay will be preferred when available."
            )

        # Error 201 ("Already paid") is deliberately excluded because it must
        # be reconciled with listpays before LNbits decides the final state.
        self.pay_failure_error_codes = {
            -32602,
            203,
            205,
            206,
            207,
            210,
            401,
        }

        self.client = self._create_client()

        # A non-zero value is treated as an explicitly configured cursor.
        # Otherwise the listener bootstraps to the current highest pay_index
        # to prevent replaying historical paid invoices at startup.
        self.last_pay_index = int(settings.clnrest_last_pay_index or 0)
        self._listener_bootstrapped = False

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as exc:
            logger.warning(f"Error closing wallet connection: {exc}")

    async def status(self) -> StatusResponse:
        try:
            logger.debug("REQUEST to /v1/listfunds")

            data = await self._rpc(
                "listfunds",
                headers=self.readonly_headers,
                timeout=15.0,
            )

            channels = data.get("channels", [])
            balance_msat = sum(
                _msat_to_int(channel.get("our_amount_msat")) for channel in channels
            )

            return StatusResponse(None, balance_msat)

        except httpx.ConnectTimeout as exc:
            logger.warning(f"CLN REST connect timeout: {exc}")
            return StatusResponse("Timed out connecting to CLN REST", 0)

        except httpx.ReadTimeout as exc:
            logger.warning(f"CLN REST read timeout: {exc}")
            return StatusResponse("CLN REST did not answer in time", 0)

        except httpx.ConnectError as exc:
            logger.warning(f"CLN REST connect error: {exc}")
            return StatusResponse("Cannot connect to CLN REST listener", 0)

        except httpx.HTTPStatusError as exc:
            error_message = self._format_http_error(exc)
            logger.warning(error_message)
            return StatusResponse(error_message, 0)

        except json.JSONDecodeError as exc:
            logger.warning(f"JSON decode error: {exc!s}")
            return StatusResponse(
                f"Failed to decode JSON response from {self.url}",
                0,
            )

        except Exception as exc:
            logger.warning(f"CLN REST status error: {exc}")
            return StatusResponse(
                f"Unable to connect to {self.url}: {exc}",
                0,
            )

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        if not self.invoice_headers:
            return InvoiceResponse(
                ok=False,
                error_message="Unable to invoice without an invoice rune",
            )

        if amount <= 0:
            return InvoiceResponse(
                ok=False,
                error_message="Invoice amount must be greater than zero",
            )

        try:
            data, preimage = self._build_invoice_payload(
                amount,
                memo,
                description_hash,
                unhashed_description,
                **kwargs,
            )

            response_data = await self._rpc(
                "invoice",
                payload=data,
                headers=self.invoice_headers,
            )

            return self._invoice_response_from_rpc(
                response_data,
                preimage,
            )

        except httpx.HTTPStatusError as exc:
            error_message = self._format_http_error(exc)
            logger.warning(f"Error creating invoice: {error_message}")
            return InvoiceResponse(
                ok=False,
                error_message=error_message,
            )

        except (UnicodeDecodeError, ValueError, UnsupportedError) as exc:
            logger.warning(f"Invalid invoice parameters: {exc}")
            return InvoiceResponse(
                ok=False,
                error_message=str(exc),
            )

        except Exception as exc:
            logger.warning(f"Error creating invoice: {exc}")
            return InvoiceResponse(
                ok=False,
                error_message=str(exc),
            )

    def _build_invoice_payload(
        self,
        amount: int,
        memo: str | None,
        description_hash: bytes | None,
        unhashed_description: bytes | None,
        **kwargs,
    ) -> tuple[dict[str, Any], str]:
        if description_hash and not unhashed_description:
            raise UnsupportedError(
                "'description_hash' requires 'unhashed_description' "
                "for Core Lightning"
            )

        preimage = (
            str(kwargs["preimage"])
            if kwargs.get("preimage")
            else random_secret_and_hash()[0]
        )

        data: dict[str, Any] = {
            "amount_msat": int(amount * 1000),
            "label": _generate_label(),
            "preimage": preimage,
        }

        self._set_invoice_description(
            data,
            memo,
            description_hash,
            unhashed_description,
        )

        if kwargs.get("expiry") is not None:
            data["expiry"] = int(kwargs["expiry"])

        return data, preimage

    def _set_invoice_description(
        self,
        data: dict[str, Any],
        memo: str | None,
        description_hash: bytes | None,
        unhashed_description: bytes | None,
    ) -> None:
        if not unhashed_description:
            data["description"] = memo or ""
            return

        description = unhashed_description.decode("utf-8")

        self._validate_description_hash(
            description_hash,
            unhashed_description,
        )

        data["description"] = description
        data["deschashonly"] = True

    @staticmethod
    def _validate_description_hash(
        description_hash: bytes | None,
        unhashed_description: bytes,
    ) -> None:
        if not description_hash:
            return

        calculated_hash = sha256(unhashed_description).digest()

        if calculated_hash != description_hash:
            raise ValueError("description_hash does not match unhashed_description")

    @staticmethod
    def _invoice_response_from_rpc(
        response_data: dict[str, Any],
        preimage: str,
    ) -> InvoiceResponse:
        payment_hash = response_data.get("payment_hash")
        bolt11 = response_data.get("bolt11")

        if not payment_hash or not bolt11:
            logger.warning("CLN invoice response missing payment_hash or bolt11")
            return InvoiceResponse(
                ok=False,
                error_message="Server error: missing required invoice fields",
            )

        if not _preimage_matches(preimage, payment_hash):
            logger.error("CLN invoice payment_hash does not match requested preimage")
            return InvoiceResponse(
                ok=False,
                error_message=(
                    "Server error: invoice preimage does not match payment_hash"
                ),
            )

        return InvoiceResponse(
            ok=True,
            checking_id=payment_hash,
            payment_request=bolt11,
            preimage=preimage,
        )

    async def pay_invoice(
        self,
        bolt11: str,
        fee_limit_msat: int,
        **_,
    ) -> PaymentResponse:
        try:
            invoice = decode(bolt11)
        except Bolt11Exception as exc:
            return PaymentResponse(
                ok=False,
                error_message=str(exc),
            )

        if not invoice.amount_msat or invoice.amount_msat <= 0:
            return PaymentResponse(
                ok=False,
                error_message="0 amount invoices are not allowed",
            )

        payment_hash = invoice.payment_hash

        if not self.pay_headers and not self.renepay_headers:
            return PaymentResponse(
                ok=False,
                checking_id=payment_hash,
                error_message=("Unable to pay invoice without a pay or renepay rune"),
            )

        existing = await self._preflight_payment(payment_hash)

        if existing:
            return existing

        method, headers, data = self._build_payment_call(
            bolt11,
            invoice.description,
            fee_limit_msat,
        )

        try:
            response_data = await self._rpc(
                method,
                payload=data,
                headers=headers,
                timeout=None,
            )

        except httpx.HTTPStatusError as exc:
            error = self._parse_rpc_http_error(exc)
            return await self._reconcile_payment_error(
                payment_hash,
                error,
            )

        except Exception as exc:
            logger.warning(
                f"Failed to pay invoice {payment_hash} using {method}: {exc}"
            )
            return await self._reconcile_payment_response(
                payment_hash,
                fallback_error=str(exc),
            )

        return await self._handle_payment_result(
            response_data,
            payment_hash,
            method,
        )

    async def _preflight_payment(
        self,
        payment_hash: str,
    ) -> PaymentResponse | None:
        try:
            found, status = await self._get_listpays_status(payment_hash)
        except Exception as exc:
            logger.debug(f"Could not preflight listpays for {payment_hash}: {exc}")
            return None

        if not found:
            return None

        if status.success:
            return PaymentResponse(
                ok=True,
                checking_id=payment_hash,
                fee_msat=status.fee_msat,
                preimage=status.preimage,
            )

        if status.paid is None:
            return PaymentResponse(
                ok=None,
                checking_id=payment_hash,
                fee_msat=status.fee_msat,
                preimage=status.preimage,
            )

        return None

    def _build_payment_call(
        self,
        bolt11: str,
        description: str | None,
        fee_limit_msat: int,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        label = _generate_label()

        if self.pay_headers:
            method = "pay"
            headers = self.pay_headers
            data: dict[str, Any] = {
                "bolt11": bolt11,
                "label": label,
                "maxfee": int(fee_limit_msat),
            }
        else:
            assert self.renepay_headers

            method = "renepay"
            headers = self.renepay_headers
            data = {
                "invstring": bolt11,
                "label": label,
                "maxfee": int(fee_limit_msat),
            }

        if description:
            data["description"] = description

        return method, headers, data

    async def _handle_payment_result(
        self,
        response_data: dict[str, Any],
        payment_hash: str,
        method: str,
    ) -> PaymentResponse:
        response_hash = response_data.get("payment_hash") or payment_hash
        status = response_data.get("status")

        if status == "complete":
            return await self._handle_complete_payment(
                response_data,
                response_hash,
                method,
            )

        if status == "pending":
            return PaymentResponse(
                ok=None,
                checking_id=response_hash,
                fee_msat=_payment_fee_msat(response_data),
            )

        error = (
            self._extract_error_message(response_data)
            or f"Unexpected Core Lightning payment status: {status!r}"
        )

        return await self._reconcile_payment_response(
            response_hash,
            fallback_error=error,
        )

    async def _handle_complete_payment(
        self,
        response_data: dict[str, Any],
        payment_hash: str,
        method: str,
    ) -> PaymentResponse:
        preimage = response_data.get("payment_preimage") or response_data.get(
            "preimage"
        )

        if not preimage:
            return await self._reconcile_payment_response(
                payment_hash,
                fallback_error=(f"{method} returned complete without a preimage"),
            )

        if not _preimage_matches(preimage, payment_hash):
            logger.error(f"{method} returned an invalid preimage/payment_hash pair")
            return PaymentResponse(
                ok=None,
                checking_id=payment_hash,
                error_message=("Core Lightning returned an invalid payment preimage"),
            )

        return PaymentResponse(
            ok=True,
            checking_id=payment_hash,
            fee_msat=_payment_fee_msat(response_data),
            preimage=preimage,
        )

    async def _reconcile_payment_error(
        self,
        payment_hash: str,
        error: dict[str, Any],
    ) -> PaymentResponse:
        reconciled = await self._reconcile_payment_response(
            payment_hash,
            fallback_error=error["message"],
        )

        if reconciled.success or reconciled.pending:
            return reconciled

        if error["terminal"]:
            return PaymentResponse(
                ok=False,
                checking_id=payment_hash,
                error_message=error["message"],
            )

        return PaymentResponse(
            ok=None,
            checking_id=payment_hash,
            error_message=error["message"],
        )

    async def get_invoice_status(
        self,
        checking_id: str,
    ) -> PaymentStatus:
        try:
            data = await self._rpc(
                "listinvoices",
                payload={"payment_hash": checking_id},
                headers=self.readonly_headers,
            )

            invoices = data.get("invoices") or []

            if not invoices:
                logger.debug(f"No CLN invoice found for payment hash {checking_id}")
                return PaymentPendingStatus()

            return self._invoice_status_from_rpc(
                checking_id,
                invoices[0],
            )

        except Exception as exc:
            logger.warning(f"Error getting invoice status for {checking_id}: {exc}")
            return PaymentPendingStatus()

    @staticmethod
    def _invoice_status_from_rpc(
        checking_id: str,
        invoice: dict[str, Any],
    ) -> PaymentStatus:
        status = invoice.get("status")

        if status == "paid":
            return _paid_invoice_status(
                checking_id,
                invoice,
            )

        if status in {"expired", "failed"}:
            return PaymentFailedStatus()

        return PaymentPendingStatus()

    async def get_payment_status(
        self,
        checking_id: str,
    ) -> PaymentStatus:
        try:
            found, status = await self._get_listpays_status(checking_id)

            if not found:
                return PaymentPendingStatus()

            return status

        except Exception as exc:
            logger.warning(f"Error getting payment status for {checking_id}: {exc}")
            return PaymentPendingStatus()

    async def paid_invoices_stream(
        self,
    ) -> AsyncGenerator[str, None]:
        """
        Emit only newly paid CLN invoices.

        When no explicit last_pay_index is configured, startup bootstraps to
        the highest existing paid pay_index before calling waitanyinvoice.
        """

        while settings.lnbits_running:
            try:
                if not self._listener_bootstrapped:
                    await self._bootstrap_listener_index()

                invoice = await self._rpc(
                    "waitanyinvoice",
                    payload={
                        "lastpay_index": self.last_pay_index,
                    },
                    headers=self.readonly_headers,
                    timeout=None,
                )

                event = self._parse_paid_invoice_event(invoice)

                if not event:
                    continue

                payment_hash, pay_index = event

                # Advance before yielding so a downstream failure does not
                # immediately replay the same invoice in this process.
                self.last_pay_index = pay_index

                logger.debug(
                    "new paid CLN invoice: "
                    f"payment_hash={payment_hash}, pay_index={pay_index}"
                )

                yield payment_hash

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                logger.debug(
                    "lost connection to corelightning-rest invoice listener: "
                    f"'{exc}', reconnecting..."
                )

                await asyncio.sleep(1.0)

    def _parse_paid_invoice_event(
        self,
        invoice: dict[str, Any],
    ) -> tuple[str, int] | None:
        if invoice.get("status") != "paid":
            return None

        payment_hash = invoice.get("payment_hash")
        pay_index = invoice.get("pay_index")

        if not payment_hash or pay_index is None:
            logger.warning("waitanyinvoice returned an incomplete paid invoice event")
            return None

        normalized_index = _normalize_pay_index(pay_index)

        if normalized_index is None:
            return None

        if normalized_index <= self.last_pay_index:
            logger.warning(
                "Ignoring stale CLN invoice event "
                f"pay_index={normalized_index}, "
                f"last_pay_index={self.last_pay_index}"
            )
            return None

        if not _event_preimage_is_valid(
            invoice,
            payment_hash,
        ):
            return None

        return payment_hash, normalized_index

    async def _bootstrap_listener_index(self) -> None:
        if self._listener_bootstrapped:
            return

        if self.last_pay_index > 0:
            logger.info(
                "Using configured CLN waitanyinvoice cursor "
                f"pay_index={self.last_pay_index}"
            )
            self._listener_bootstrapped = True
            return

        logger.info("Bootstrapping CLN invoice listener to current pay_index")

        data = await self._fetch_bootstrap_invoices()

        self.last_pay_index = _highest_paid_pay_index(data.get("invoices") or [])
        self._listener_bootstrapped = True

        logger.info(
            "CLN invoice listener bootstrapped at "
            f"pay_index={self.last_pay_index}; "
            "historical paid invoices will not be replayed"
        )

    async def _fetch_bootstrap_invoices(
        self,
    ) -> dict[str, Any]:
        try:
            return await self._rpc(
                "listinvoices",
                headers=self.readonly_headers,
                timeout=30.0,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            logger.warning(f"Unable to bootstrap CLN invoice listener safely: {exc}")
            raise

    async def _get_listpays_status(
        self,
        checking_id: str,
    ) -> tuple[bool, PaymentStatus]:
        data = await self._rpc(
            "listpays",
            payload={"payment_hash": checking_id},
            headers=self.readonly_headers,
        )

        pays = data.get("pays") or []

        if not pays:
            return False, PaymentPendingStatus()

        pay = _select_best_pay(pays)

        return True, _payment_status_from_pay(
            checking_id,
            pay,
        )

    async def _reconcile_payment_response(
        self,
        payment_hash: str,
        fallback_error: str,
    ) -> PaymentResponse:
        try:
            found, status = await self._get_listpays_status(payment_hash)
        except Exception as exc:
            logger.warning(f"Could not reconcile payment {payment_hash}: {exc}")
            return PaymentResponse(
                ok=None,
                checking_id=payment_hash,
                error_message=fallback_error,
            )

        if not found:
            return PaymentResponse(
                ok=None,
                checking_id=payment_hash,
                error_message=fallback_error,
            )

        if status.success:
            return PaymentResponse(
                ok=True,
                checking_id=payment_hash,
                fee_msat=status.fee_msat,
                preimage=status.preimage,
            )

        if status.failed:
            return PaymentResponse(
                ok=False,
                checking_id=payment_hash,
                error_message=fallback_error,
            )

        return PaymentResponse(
            ok=None,
            checking_id=payment_hash,
            fee_msat=status.fee_msat,
            preimage=status.preimage,
            error_message=fallback_error,
        )

    async def _rpc(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = 30.0,
    ) -> dict[str, Any]:
        response = await self.client.post(
            f"/v1/{method}",
            json=payload or {},
            headers=headers,
            timeout=timeout,
        )

        parsed_body = self._decode_response_json(
            response,
        )

        if response.is_error:
            message = (
                self._extract_error_message(parsed_body)
                if isinstance(parsed_body, dict)
                else None
            )

            raise httpx.HTTPStatusError(
                message or f"CLN REST returned HTTP {response.status_code}",
                request=response.request,
                response=response,
            )

        if parsed_body is None:
            raise json.JSONDecodeError(
                f"Invalid JSON response from CLN REST {method}",
                response.text,
                0,
            )

        if not isinstance(parsed_body, dict):
            raise ValueError(
                f"Unexpected CLN response type for {method}: " f"{type(parsed_body)!r}"
            )

        self._raise_for_rpc_error(
            method,
            parsed_body,
        )

        return parsed_body

    @staticmethod
    def _decode_response_json(
        response: httpx.Response,
    ) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError:
            return None

    def _raise_for_rpc_error(
        self,
        method: str,
        data: dict[str, Any],
    ) -> None:
        if "error" in data:
            message = (
                self._extract_error_message(data)
                or f"Core Lightning RPC '{method}' returned an error"
            )
            raise ValueError(message)

        if data.get("code") is not None and data.get("message"):
            raise ValueError(str(data["message"]))

    def _format_http_error(
        self,
        exc: httpx.HTTPStatusError,
    ) -> str:
        message = f"CLN REST HTTP {exc.response.status_code}"

        try:
            data = exc.response.json()
            extracted = self._extract_error_message(data)

            if extracted:
                return f"{message}: {extracted}"

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as parse_exc:
            logger.debug(f"Could not parse CLN REST error body: {parse_exc}")

        body = exc.response.text.strip()

        if body:
            return f"{message}: {body}"

        return message

    def _parse_rpc_http_error(
        self,
        exc: httpx.HTTPStatusError,
    ) -> dict[str, Any]:
        message = self._format_http_error(exc)
        code = self._extract_rpc_error_code(exc)

        return {
            "message": message,
            "code": code,
            "terminal": code in self.pay_failure_error_codes,
        }

    @staticmethod
    def _extract_rpc_error_code(
        exc: httpx.HTTPStatusError,
    ) -> int | None:
        try:
            data = exc.response.json()
            error = data.get("error")

            raw_code = (
                error.get("code") if isinstance(error, dict) else data.get("code")
            )

            if raw_code is None:
                return None

            return int(raw_code)

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as parse_exc:
            logger.debug(f"Could not parse CLN RPC error code: {parse_exc}")
            return None

    @staticmethod
    def _extract_error_message(
        data: dict[str, Any] | None,
    ) -> str | None:
        if not data:
            return None

        error = data.get("error")

        if isinstance(error, dict):
            message = error.get("message")

            if message:
                return str(message)

            return str(error)

        if isinstance(error, str):
            return error

        message = data.get("message")

        if message:
            return str(message)

        detail = data.get("detail")

        if detail:
            return str(detail)

        return None

    def _create_client(self) -> httpx.AsyncClient:
        parsed_url = urlparse(self.url)

        if parsed_url.scheme == "http":
            return self._create_http_client(
                parsed_url.hostname,
            )

        if parsed_url.scheme == "https":
            return self._create_https_client()

        raise ValueError("CLNREST_URL must start with http:// or https://")

    def _create_http_client(
        self,
        hostname: str | None,
    ) -> httpx.AsyncClient:
        if hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError(
                "Insecure HTTP connections are only allowed for localhost "
                "or equivalent loopback IP addresses. Set CLNREST_URL to "
                "https:// for external connections."
            )

        logger.warning("Not using TLS for local CLNRestWallet connection")

        return httpx.AsyncClient(
            base_url=self.url,
        )

    def _create_https_client(self) -> httpx.AsyncClient:
        logger.info(f"Using TLS to connect to {self.url}")

        if not settings.clnrest_ca:
            raise ValueError("CLNREST_CA is required for an HTTPS CLN REST connection")

        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        self._load_ca_certificate(
            ssl_context,
            settings.clnrest_ca,
        )

        # Certificate-chain verification remains enabled. Hostname matching is
        # disabled for compatibility with common localhost/IP CLN deployments.
        ssl_context.check_hostname = False

        return httpx.AsyncClient(
            base_url=self.url,
            verify=ssl_context,
        )

    @staticmethod
    def _load_ca_certificate(
        ssl_context: ssl.SSLContext,
        ca_setting: str,
    ) -> None:
        if os.path.isfile(ca_setting):
            logger.info(f"Using CLN REST CA file: {ca_setting}")
            ssl_context.load_verify_locations(
                cafile=ca_setting,
            )
            return

        logger.info("Using CLN REST CA certificate from configured PEM content")

        ssl_context.load_verify_locations(
            cadata=ca_setting.replace("\\n", "\n"),
        )


def _paid_invoice_status(
    checking_id: str,
    invoice: dict[str, Any],
) -> PaymentStatus:
    preimage = invoice.get("payment_preimage") or invoice.get("preimage")

    if not preimage:
        logger.error(f"Paid CLN invoice {checking_id} has no preimage")
        return PaymentPendingStatus()

    if not _preimage_matches(
        preimage,
        checking_id,
    ):
        logger.error(f"Paid CLN invoice {checking_id} returned an invalid preimage")
        return PaymentPendingStatus()

    fee_msat = _msat_to_int(invoice.get("amount_received_msat")) - _msat_to_int(
        invoice.get("amount_msat")
    )

    return PaymentSuccessStatus(
        fee_msat=fee_msat,
        preimage=preimage,
    )


def _payment_status_from_pay(
    checking_id: str,
    pay: dict[str, Any],
) -> PaymentStatus:
    status = pay.get("status")

    if status == "complete":
        return _completed_payment_status(
            checking_id,
            pay,
        )

    if status == "failed":
        return PaymentFailedStatus()

    return PaymentPendingStatus(
        fee_msat=_payment_fee_msat(pay),
    )


def _completed_payment_status(
    checking_id: str,
    pay: dict[str, Any],
) -> PaymentStatus:
    preimage = pay.get("preimage") or pay.get("payment_preimage")

    if not preimage:
        logger.error(f"Completed payment {checking_id} has no preimage")
        return PaymentPendingStatus()

    if not _preimage_matches(
        preimage,
        checking_id,
    ):
        logger.error(f"Completed payment {checking_id} has an invalid preimage")
        return PaymentPendingStatus()

    return PaymentSuccessStatus(
        fee_msat=_payment_fee_msat(pay),
        preimage=preimage,
    )


def _preimage_matches(
    preimage: str,
    payment_hash: str,
) -> bool:
    try:
        return verify_preimage(
            preimage,
            payment_hash,
        )
    except (TypeError, ValueError):
        return False


def _normalize_pay_index(
    value: Any,
) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid Core Lightning pay_index: {value!r}")
        return None


def _highest_paid_pay_index(
    invoices: list[dict[str, Any]],
) -> int:
    indexes = [
        normalized
        for invoice in invoices
        if invoice.get("status") == "paid"
        if invoice.get("pay_index") is not None
        if (normalized := _normalize_pay_index(invoice.get("pay_index"))) is not None
    ]

    return max(
        indexes,
        default=0,
    )


def _event_preimage_is_valid(
    invoice: dict[str, Any],
    payment_hash: str,
) -> bool:
    preimage = invoice.get("payment_preimage") or invoice.get("preimage")

    if not preimage:
        return True

    if _preimage_matches(
        preimage,
        payment_hash,
    ):
        return True

    logger.error(
        "waitanyinvoice returned invalid preimage " f"for payment_hash={payment_hash}"
    )

    return False


def _msat_to_int(
    value: Any,
) -> int:
    if value is None:
        return 0

    if isinstance(
        value,
        (int, float),
    ):
        return int(value)

    if isinstance(value, str):
        amount = value.strip()

        if amount.endswith("msat"):
            amount = amount[:-4]

        return int(amount)

    if isinstance(value, dict):
        if "msat" in value:
            return _msat_to_int(value["msat"])

        if "amount_msat" in value:
            return _msat_to_int(value["amount_msat"])

    raise TypeError(f"Unsupported Core Lightning msat value: {value!r}")


def _payment_fee_msat(
    payment: dict[str, Any],
) -> int | None:
    amount_sent = payment.get("amount_sent_msat")
    amount = payment.get("amount_msat")

    if amount_sent is None or amount is None:
        return None

    return _msat_to_int(amount_sent) - _msat_to_int(amount)


def _select_best_pay(
    pays: list[dict[str, Any]],
) -> dict[str, Any]:
    complete = [payment for payment in pays if payment.get("status") == "complete"]

    if complete:
        return complete[-1]

    pending = [payment for payment in pays if payment.get("status") == "pending"]

    if pending:
        return pending[-1]

    failed = [payment for payment in pays if payment.get("status") == "failed"]

    if failed:
        return failed[-1]

    return pays[-1]


def _generate_label() -> str:
    random_uuid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode()

    return f"LNbits_{random_uuid}"
