import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import httpx
from bolt11 import decode as bolt11_decode
from loguru import logger
from websockets import connect

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings

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


class BarkError(Exception):
    pass


class BarkHTTPError(BarkError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class BarkWallet(Wallet):
    """https://second.tech/docs/barkd"""

    def __init__(self):
        if not settings.bark_api_endpoint:
            raise ValueError("cannot initialize BarkWallet: missing bark_api_endpoint")
        if not settings.bark_api_token:
            raise ValueError("cannot initialize BarkWallet: missing bark_api_token")

        super().__init__()
        self.endpoint = normalize_endpoint(settings.bark_api_endpoint)
        parsed_endpoint = urlsplit(self.endpoint)
        ws_scheme = "wss" if parsed_endpoint.scheme == "https" else "ws"
        self.ws_endpoint = urlunsplit(
            (
                ws_scheme,
                parsed_endpoint.netloc,
                "/api/v1/notifications/ws",
                "",
                "",
            )
        )
        self.headers = {
            "Authorization": f"Bearer {settings.bark_api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.headers)
        self.pending_payments: dict[str, str] = {}
        self.outgoing_payment_waiters: dict[str, asyncio.Future[PaymentStatus]] = {}
        self.notified_paid_invoice: str | None = None

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            connected = await self._request_json(
                "GET", "/api/v1/wallet/connected", timeout=10
            )
            if not connected.get("connected"):
                return StatusResponse("Bark wallet is not connected to Ark server.", 0)

            data = await self._request_json("GET", "/api/v1/wallet/balance", timeout=10)
            if "spendable_sat" not in data:
                return StatusResponse("Server error: 'missing required fields'", 0)

            return StatusResponse(None, int(data["spendable_sat"]) * 1000)
        except BarkError as exc:
            return StatusResponse(str(exc), 0)
        except Exception as exc:
            logger.warning(exc)
            return StatusResponse(f"Unable to connect to {self.endpoint}.", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        if description_hash or unhashed_description:
            return InvoiceResponse(
                ok=False,
                error_message="Bark does not support description-hash invoices.",
            )

        payload: dict[str, Any] = {"amount_sat": int(amount)}
        if memo is not None:
            payload["description"] = memo

        try:
            data = await self._request_json(
                "POST",
                "/api/v1/lightning/receives/invoice",
                json=payload,
                timeout=40,
            )
            payment_request = data["invoice"]
            checking_id = bolt11_decode(payment_request).payment_hash

            return InvoiceResponse(
                ok=True,
                checking_id=checking_id,
                payment_request=payment_request,
            )
        except KeyError as exc:
            logger.warning(exc)
            return InvoiceResponse(
                ok=False, error_message="Server error: 'missing required fields'"
            )
        except BarkError as exc:
            return InvoiceResponse(ok=False, error_message=str(exc))
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        decoded = self._decode_invoice_for_payment(bolt11)
        if isinstance(decoded, PaymentResponse):
            return decoded

        checking_id, amount_sat = decoded
        fee_response = await self._check_fee_limit(
            checking_id, amount_sat, fee_limit_msat
        )
        if fee_response:
            return fee_response

        return await self._send_payment(bolt11, checking_id)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            identifier = quote(checking_id, safe="")
            data = await self._request_json(
                "GET", f"/api/v1/lightning/receives/{identifier}"
            )
        except BarkHTTPError as exc:
            notification_status = self._consume_paid_invoice_notification(checking_id)
            if notification_status:
                return notification_status
            if exc.status_code == 404:
                return PaymentFailedStatus()
            logger.warning(exc)
            return PaymentPendingStatus()
        except Exception as exc:
            logger.warning(exc)
            notification_status = self._consume_paid_invoice_notification(checking_id)
            if notification_status:
                return notification_status
            return PaymentPendingStatus()

        return self._invoice_status_from_response(checking_id, data)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            data = await self._request_json("GET", "/api/v1/history")
            if not isinstance(data, list):
                return PaymentPendingStatus()

            for movement in data:
                if self._movement_matches_payment_hash(movement, checking_id):
                    return self._movement_to_payment_status(movement)
        except Exception as exc:
            logger.warning(exc)

        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                async for checking_id in self._listen_paid_invoices():
                    yield checking_id
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Bark invoices stream unavailable "
                    f"({type(exc).__name__}); retrying in 5 seconds."
                )
                await asyncio.sleep(5)

    async def _listen_paid_invoices(self) -> AsyncGenerator[str, None]:
        ticket = await self._request_json(
            "GET", "/api/v1/notifications/ws/ticket", timeout=10
        )
        if not isinstance(ticket, str) or not ticket:
            raise BarkError("Server error: 'invalid websocket ticket'")

        ws_url = f"{self.ws_endpoint}?{urlencode({'ticket': ticket})}"
        async with connect(ws_url) as ws:
            logger.info("Connected to Bark invoices stream.")

            while settings.lnbits_running:
                notification = self._parse_notification(await ws.recv())
                if not notification:
                    continue
                if notification.get("type") == "channel-lagging":
                    logger.warning(
                        "Bark invoice notifications were lost; pending payments "
                        "will be reconciled by the scheduled check."
                    )
                    continue

                self._notify_outgoing_payment(notification)
                checking_id = self._incoming_payment_hash(notification)
                if checking_id:
                    self.notified_paid_invoice = checking_id
                    yield checking_id

    def _parse_notification(self, message: str | bytes) -> dict[str, Any] | None:
        try:
            notification = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid message from Bark invoices stream.")
            return None
        return notification if isinstance(notification, dict) else None

    def _incoming_payment_hash(self, notification: dict[str, Any]) -> str | None:
        if notification.get("type") not in {
            "movement-created",
            "movement-updated",
        }:
            return None

        movement = notification.get("movement")
        if not isinstance(movement, dict) or movement.get("status") != "successful":
            return None

        for destination in movement.get("received_on") or []:
            if not isinstance(destination, dict):
                continue
            method = destination.get("destination")
            if not isinstance(method, dict) or method.get("type") != "invoice":
                continue
            invoice = method.get("value")
            if not isinstance(invoice, str):
                continue
            try:
                return bolt11_decode(invoice).payment_hash
            except Exception as exc:
                logger.debug(f"Unable to decode Bark notification invoice: {exc}")
        return None

    def _consume_paid_invoice_notification(
        self, checking_id: str, preimage: str | None = None
    ) -> PaymentStatus | None:
        if checking_id != self.notified_paid_invoice:
            return None
        self.notified_paid_invoice = None
        return PaymentSuccessStatus(preimage=preimage)

    def _invoice_status_from_response(
        self, checking_id: str, data: Any
    ) -> PaymentStatus:
        preimage = data.get("payment_preimage") if isinstance(data, dict) else None
        notification_status = self._consume_paid_invoice_notification(
            checking_id, preimage
        )
        if notification_status:
            return notification_status
        if not isinstance(data, dict):
            return PaymentPendingStatus()
        if data.get("state") == "settled" or data.get("settled_at"):
            return PaymentSuccessStatus(preimage=preimage)
        if not data.get("finished_at"):
            return PaymentPendingStatus()
        if data.get("preimage_revealed_at"):
            return PaymentSuccessStatus(preimage=preimage)
        return PaymentFailedStatus()

    def _decode_invoice_for_payment(
        self, bolt11: str
    ) -> tuple[str, int] | PaymentResponse:
        try:
            invoice = bolt11_decode(bolt11)
            checking_id = invoice.payment_hash
        except Exception as exc:
            logger.warning(exc)
            return PaymentResponse(ok=False, error_message=f"Invalid invoice: {exc!s}")

        if not invoice.amount_msat or invoice.amount_msat <= 0:
            return PaymentResponse(
                ok=False,
                checking_id=checking_id,
                error_message="Bark 0 amount invoice not supported.",
            )

        amount_sat = (int(invoice.amount_msat) + 999) // 1000
        return checking_id, amount_sat

    async def _check_fee_limit(
        self, checking_id: str, amount_sat: int, fee_limit_msat: int
    ) -> PaymentResponse | None:
        try:
            fee_estimate = await self._request_json(
                "GET",
                "/api/v1/fees/lightning/pay",
                params={"amount_sat": amount_sat},
                timeout=30,
            )
            fee_msat = int(fee_estimate["fee_sat"]) * 1000
            if fee_msat > fee_limit_msat:
                return PaymentResponse(
                    ok=False,
                    checking_id=checking_id,
                    fee_msat=fee_msat,
                    error_message=(
                        f"fee of {fee_msat} msat exceeds limit of "
                        f"{fee_limit_msat} msat"
                    ),
                )
        except KeyError as exc:
            logger.warning(exc)
            return PaymentResponse(
                ok=False,
                checking_id=checking_id,
                error_message="Server error: 'missing required fields'",
            )
        except BarkError as exc:
            return PaymentResponse(
                ok=False, checking_id=checking_id, error_message=str(exc)
            )
        return None

    async def _send_payment(self, bolt11: str, checking_id: str) -> PaymentResponse:
        waiter = asyncio.get_running_loop().create_future()
        self.outgoing_payment_waiters[checking_id] = waiter
        try:
            initiation_error = await self._initiate_payment(bolt11, checking_id)
            if initiation_error is not None:
                return initiation_error

            self.pending_payments[checking_id] = bolt11
            response = await self._payment_response_from_status(checking_id)
            if not response.pending:
                return response

            wait_seconds = max(
                0, settings.lnbits_funding_source_pay_invoice_wait_seconds - 1
            )
            if not wait_seconds:
                return response
            try:
                status = await asyncio.wait_for(waiter, timeout=wait_seconds)
            except TimeoutError:
                return response
            return self._payment_response(checking_id, status)
        finally:
            current_waiter = self.outgoing_payment_waiters.pop(checking_id, None)
            if current_waiter and not current_waiter.done():
                current_waiter.cancel()

    async def _initiate_payment(
        self, bolt11: str, checking_id: str
    ) -> PaymentResponse | None:
        try:
            r = await self.client.post(
                "/api/v1/lightning/pay",
                json={"destination": bolt11},
                timeout=40,
            )
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict) or not isinstance(data.get("message"), str):
                return self._pending_payment_response(
                    bolt11,
                    checking_id,
                    "Server error: 'invalid payment response'",
                )
        except httpx.TimeoutException:
            message = f"Timeout connecting to {self.endpoint}. keep pending..."
            logger.warning(message)
            return self._pending_payment_response(bolt11, checking_id, message)
        except httpx.HTTPStatusError as exc:
            if exc.response.is_client_error:
                return PaymentResponse(
                    ok=False,
                    checking_id=checking_id,
                    error_message=self._http_error_message(exc.response),
                )
            message = self._http_error_message(exc.response)
            logger.warning(message)
            return self._pending_payment_response(bolt11, checking_id, message)
        except httpx.RequestError as exc:
            message = f"Unable to connect to {self.endpoint}. keep pending..."
            logger.warning(message)
            logger.warning(exc)
            return self._pending_payment_response(bolt11, checking_id, message)
        except json.JSONDecodeError:
            return self._pending_payment_response(
                bolt11,
                checking_id,
                "Server error: 'invalid json response'",
            )
        except Exception as exc:
            message = f"Unable to connect to {self.endpoint}. keep pending..."
            logger.warning(exc)
            return self._pending_payment_response(bolt11, checking_id, message)
        return None

    def _pending_payment_response(
        self, bolt11: str, checking_id: str, error_message: str
    ) -> PaymentResponse:
        self.pending_payments[checking_id] = bolt11
        return PaymentResponse(
            ok=None,
            checking_id=checking_id,
            error_message=error_message,
        )

    async def _payment_response_from_status(self, checking_id: str) -> PaymentResponse:
        status = await self.get_payment_status(checking_id)
        return self._payment_response(checking_id, status)

    def _payment_response(
        self, checking_id: str, status: PaymentStatus
    ) -> PaymentResponse:
        if status.success:
            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=status.fee_msat,
                preimage=status.preimage,
            )
        if status.failed:
            return PaymentResponse(ok=False, checking_id=checking_id)
        return PaymentResponse(ok=None, checking_id=checking_id)

    def _notify_outgoing_payment(self, notification: dict[str, Any]) -> None:
        if notification.get("type") not in {
            "movement-created",
            "movement-updated",
        }:
            return

        movement = notification.get("movement")
        if not isinstance(movement, dict):
            return
        status = self._movement_to_payment_status(movement)
        if status.pending:
            return

        for destination in movement.get("sent_to") or []:
            if not isinstance(destination, dict):
                continue
            method = destination.get("destination")
            if not isinstance(method, dict) or method.get("type") != "invoice":
                continue
            invoice = method.get("value")
            if not isinstance(invoice, str):
                continue
            try:
                checking_id = bolt11_decode(invoice).payment_hash
            except Exception as exc:
                logger.debug(f"Unable to decode Bark notification invoice: {exc}")
                continue

            waiter = self.outgoing_payment_waiters.get(checking_id)
            if waiter and not waiter.done():
                waiter.set_result(status)
            return

    async def _request_json(self, method: str, path: str, **kwargs) -> Any:
        try:
            r = await self.client.request(method, path, **kwargs)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            raise BarkHTTPError(
                self._http_error_message(exc.response), exc.response.status_code
            ) from exc
        except json.JSONDecodeError as exc:
            raise BarkError("Server error: 'invalid json response'") from exc
        except httpx.RequestError as exc:
            raise BarkError(f"Unable to connect to {self.endpoint}.") from exc

    def _http_error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except json.JSONDecodeError:
            return response.text or f"HTTP {response.status_code}"

        if isinstance(data, dict):
            for key in ("message", "detail", "error"):
                if key in data:
                    return f"Server error: '{data[key]}'"
        return response.text or f"HTTP {response.status_code}"

    def _movement_matches_payment_hash(self, movement: Any, checking_id: str) -> bool:
        if not isinstance(movement, dict):
            return False

        metadata_hash = self._find_value(
            movement.get("metadata"), {"payment_hash", "paymentHash"}
        )
        if metadata_hash == checking_id:
            return True

        for destination in movement.get("sent_to") or []:
            if not isinstance(destination, dict):
                continue
            method = destination.get("destination")
            if not isinstance(method, dict) or method.get("type") != "invoice":
                continue

            invoice = method.get("value")
            if not isinstance(invoice, str):
                continue

            if invoice == self.pending_payments.get(checking_id):
                return True

            try:
                if bolt11_decode(invoice).payment_hash == checking_id:
                    return True
            except Exception as exc:
                logger.debug(f"Unable to decode Bark history invoice: {exc}")
                continue

        return False

    def _movement_to_payment_status(self, movement: dict[str, Any]) -> PaymentStatus:
        status = movement.get("status")
        if status == "successful":
            fee_sat = movement.get("offchain_fee_sat")
            fee_msat = int(fee_sat) * 1000 if fee_sat is not None else None
            preimage = self._find_value(
                movement.get("metadata"),
                {"preimage", "payment_preimage", "paymentPreimage"},
            )
            return PaymentSuccessStatus(fee_msat=fee_msat, preimage=preimage)
        if status in {"failed", "canceled"}:
            return PaymentFailedStatus()
        return PaymentPendingStatus()

    def _find_value(self, data: Any, keys: set[str]) -> str | None:
        if isinstance(data, dict):
            for key, value in data.items():
                if key in keys and isinstance(value, str):
                    return value
            for value in data.values():
                found = self._find_value(value, keys)
                if found:
                    return found
        if isinstance(data, list):
            for value in data:
                found = self._find_value(value, keys)
                if found:
                    return found
        return None
