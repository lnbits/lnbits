import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import httpx
from bolt11 import decode as bolt11_decode
from loguru import logger

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


class SparkSidecarError(Exception):
    pass


class SparkL2Wallet(Wallet):
    """
    Spark L2 funding source via a local sidecar service.

    Required settings/env:
      - SPARK_L2_ENDPOINT (default http://127.0.0.1:8765)
    Optional:
      - SPARK_L2_API_KEY
    """

    def __init__(self):
        self._status = "Initializing"
        self._sidecar_path = Path(settings.lnbits_data_folder, "light_spark")

        self.pending_invoices: list[str] = []

        self.endpoint = "http://127.0.0.1:8765"
        self._api_key = uuid.uuid4().hex

        if settings.spark_l2_external_endpoint:
            self.endpoint = normalize_endpoint(
                cast(str, settings.spark_l2_external_endpoint)
            )
            logger.info(f"Using external Spark sidecar endpoint: {self.endpoint}")
        else:
            logger.error("No Spark sidecar endpoint configuration found.")

        if settings.spark_l2_external_api_key:
            self._api_key = cast(str, settings.spark_l2_external_api_key)
            logger.info("Using external Spark sidecar API.")
        else:
            logger.warning("No Spark sidecar API key configured.")

        headers = {"User-Agent": settings.user_agent, "X-Api-Key": self._api_key}

        self.client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers=headers,
            timeout=60,
        )

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            res = await self._request("POST", "/v1/balance")
            balance_msat = res.get("balance_msat")
            if balance_msat is not None:
                return StatusResponse(None, int(balance_msat))
            balance_sats = res.get("balance_sats")
            if balance_sats is None:
                return StatusResponse("Spark sidecar: missing balance.", 0)
            return StatusResponse(None, int(balance_sats) * 1000)
        except Exception as e:
            logger.warning(e)
            return StatusResponse(f"Spark sidecar status error: {e}", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        expiry = kwargs.get("expiry")
        expiry_secs = int(expiry) if expiry else None

        description_hash_hex = None
        if description_hash:
            description_hash_hex = description_hash.hex()
        elif unhashed_description:
            description_hash_hex = hashlib.sha256(unhashed_description).hexdigest()

        try:
            payload = {
                "amount_sats": int(amount),
                "memo": (memo or "") if not description_hash_hex else None,
                "description_hash": description_hash_hex,
                "expiry_seconds": expiry_secs,
            }
            res = await self._request("POST", "/v1/invoices", payload)
            bolt11 = res.get("payment_request")
            checking_id = res.get("checking_id")
            if not bolt11 or not checking_id:
                return InvoiceResponse(
                    ok=False,
                    error_message="Spark sidecar invoice response missing fields.",
                )
            self.pending_invoices.append(checking_id)

            return InvoiceResponse(
                ok=True,
                payment_request=bolt11,
                checking_id=checking_id,
                preimage=res.get("preimage", None),
            )
        except Exception as e:
            return InvoiceResponse(ok=False, error_message=str(e))

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            max_fee_sats = (int(fee_limit_msat) + 999) // 1000

            payment_hash = None
            try:
                payment_hash = bolt11_decode(bolt11).payment_hash
            except Exception as exc:
                logger.warning(exc)
                payment_hash = None
            payload = {
                "bolt11": bolt11,
                "max_fee_sats": max_fee_sats,
                "payment_hash": payment_hash,
            }
            res = await self._request("POST", "/v1/payments", payload)
            checking_id = payment_hash or res.get("checking_id")
            if not checking_id:
                return PaymentResponse(
                    ok=False,
                    error_message="Spark sidecar payment response missing checking_id.",
                )
            status = res.get("status")
            fee_msat = res.get("fee_msat")
            ok = None
            if status:
                ok = self._map_payment_ok(status)
            return PaymentResponse(
                ok=ok,
                checking_id=checking_id,
                fee_msat=int(fee_msat) if fee_msat is not None else None,
                preimage=res.get("preimage"),
            )

        except Exception as e:
            return PaymentResponse(ok=False, error_message=str(e))

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            res = await self._request("GET", f"/v1/invoices/{checking_id}")
            status = res.get("status")
            if not status:
                return PaymentPendingStatus()
            return self._map_invoice_status(status)
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            res = await self._request("GET", f"/v1/payments/{checking_id}")
            status = res.get("status")
            fee_msat = res.get("fee_msat")
            preimage = res.get("preimage")
            if not status:
                return PaymentPendingStatus()
            mapped = self._map_payment_status(status)
            if mapped.success:
                return PaymentSuccessStatus(
                    fee_msat=int(fee_msat) if fee_msat is not None else None,
                    preimage=preimage,
                )
            if mapped.failed:
                return PaymentFailedStatus()
            return PaymentPendingStatus()
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        stream_path = "/v1/invoices/stream"
        while settings.lnbits_running:
            try:
                async with self.client.stream("GET", stream_path, timeout=None) as r:
                    if r.status_code in {404, 405}:
                        logger.warning(
                            "Spark sidecar invoice stream not available, "
                            "falling back to polling."
                        )
                        async for checking_id in self._poll_pending_invoices():
                            yield checking_id
                        return
                    r.raise_for_status()
                    logger.info("connected to Spark sidecar invoice stream.")
                    async for line in r.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = json.loads(line[5:].strip())
                        checking_id = data.get("checking_id")
                        if not checking_id:
                            continue
                        yield checking_id
            except Exception as exc:
                logger.error(
                    "lost connection to Spark sidecar invoice stream: "
                    f"'{exc}' retrying in 5 seconds"
                )
                await asyncio.sleep(5)

    async def _request(
        self, method: str, path: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        error_message = None
        try:
            r = await self.client.request(method, path, json=json_data)
            r.raise_for_status()
            j = r.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                try:
                    error_json = exc.response.json()
                    if "error" in error_json:
                        error_message = error_json["error"]
                except Exception as json_exc:
                    logger.error(
                        f"Failed to parse Spark error response as JSON: {json_exc}"
                    )
            raise SparkSidecarError(
                error_message or f"Spark sidecar request error: '{exc}'"
            ) from exc

        if error_message or j.get("error"):
            raise SparkSidecarError(
                error_message or f"Spark sidecar error: {j['error']}"
            )
        return j

    async def _poll_pending_invoices(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            for invoice in list(self.pending_invoices):
                try:
                    status = await self.get_invoice_status(invoice)
                    if status.paid:
                        yield invoice
                        self.pending_invoices.remove(invoice)
                    elif status.failed:
                        self.pending_invoices.remove(invoice)
                except Exception as exc:
                    logger.error(f"could not get status of invoice {invoice}: '{exc}' ")
            await asyncio.sleep(5)

    def _map_invoice_status(self, status: str) -> PaymentStatus:
        success = {
            "LIGHTNING_PAYMENT_RECEIVED",
            "TRANSFER_COMPLETED",
            "PAYMENT_PREIMAGE_RECOVERED",
        }
        failed = {
            "TRANSFER_FAILED",
            "PAYMENT_PREIMAGE_RECOVERING_FAILED",
            "REFUND_SIGNING_FAILED",
            "REFUND_SIGNING_COMMITMENTS_QUERYING_FAILED",
            "TRANSFER_CREATION_FAILED",
        }
        if status in success:
            return PaymentSuccessStatus()
        if status in failed:
            return PaymentFailedStatus()
        return PaymentPendingStatus()

    def _map_payment_status(self, status: str) -> PaymentStatus:
        success = {
            "LIGHTNING_PAYMENT_SUCCEEDED",
            "TRANSFER_COMPLETED",
            "PREIMAGE_PROVIDED",
        }
        failed = {
            "LIGHTNING_PAYMENT_FAILED",
            "TRANSFER_FAILED",
            "PREIMAGE_PROVIDING_FAILED",
            "USER_TRANSFER_VALIDATION_FAILED",
            "USER_SWAP_RETURN_FAILED",
        }
        if status in success:
            return PaymentSuccessStatus()
        if status in failed:
            return PaymentFailedStatus()
        return PaymentPendingStatus()

    def _map_payment_ok(self, status: str) -> bool | None:
        mapped = self._map_payment_status(status)
        if mapped.success:
            return True
        if mapped.failed:
            return False
        return None
