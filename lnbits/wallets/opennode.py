import asyncio
from collections.abc import AsyncGenerator

import httpx
from bolt11 import Bolt11Exception
from bolt11 import decode as bolt11_decode
from loguru import logger

from lnbits.exceptions import UnsupportedError
from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class OpenNodeWallet(Wallet):
    """https://developers.opennode.com/"""

    def __init__(self):
        if not settings.opennode_api_endpoint:
            raise ValueError(
                "cannot initialize OpenNodeWallet: missing opennode_api_endpoint"
            )
        super().__init__()
        key = (
            settings.opennode_key
            or settings.opennode_admin_key
            or settings.opennode_invoice_key
        )
        if not key:
            raise ValueError(
                "cannot initialize OpenNodeWallet: "
                "missing opennode_key or opennode_admin_key or opennode_invoice_key"
            )
        self.key = key

        self.endpoint = normalize_endpoint(settings.opennode_api_endpoint)
        self.payment_ids: dict[str, str] = {}

        headers = {
            "Authorization": self.key,
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=headers)

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get("/v1/account/balance", timeout=40)
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse(f"Unable to connect to '{self.endpoint}'", 0)

        if r.is_error:
            error_message = r.json()["message"]
            return StatusResponse(error_message, 0)

        data = r.json()["data"]
        # multiply balance by 1000 to get msats balance
        return StatusResponse(None, data["balance"]["BTC"] * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        if description_hash or unhashed_description:
            raise UnsupportedError("description_hash")

        r = await self.client.post(
            "/v1/charges",
            json={
                "amount": amount,
                "description": memo or "",
            },
            timeout=40,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return InvoiceResponse(ok=False, error_message=error_message)

        data = r.json()["data"]
        checking_id = data["id"]
        payment_request = data["lightning_invoice"]["payreq"]
        self.pending_invoices.append(checking_id)
        return InvoiceResponse(
            ok=True, checking_id=checking_id, payment_request=payment_request
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            checking_id = bolt11_decode(bolt11).payment_hash
        except Bolt11Exception as exc:
            return PaymentResponse(ok=False, error_message=str(exc))

        try:
            r = await self.client.post(
                "/v2/withdrawals",
                json={"type": "ln", "address": bolt11},
                timeout=None,
            )
            data = r.json()
        except Exception as exc:
            logger.warning(exc)
            return PaymentResponse(
                checking_id=checking_id,
                error_message="Unable to determine payment status.",
            )

        if r.is_error:
            error_message = data.get("message", r.text)
            logger.warning(error_message)
            return PaymentResponse(
                ok=False if r.is_client_error else None,
                checking_id=checking_id,
                error_message=error_message,
            )

        try:
            payment_data = data["data"]
            provider_id = payment_data["id"]
        except (KeyError, TypeError) as exc:
            logger.warning(exc)
            return PaymentResponse(
                checking_id=checking_id,
                error_message="Server error: 'missing required fields'",
            )

        self.payment_ids[checking_id] = provider_id
        try:
            fee_msat = -payment_data["fee"] * 1000
            status = payment_data["status"]
        except (KeyError, TypeError) as exc:
            logger.warning(exc)
            return PaymentResponse(
                checking_id=checking_id,
                error_message="Server error: 'missing required fields'",
            )

        if status in {"paid", "confirmed"}:
            return PaymentResponse(ok=True, checking_id=checking_id, fee_msat=fee_msat)
        if status in {"error", "failed"}:
            self.payment_ids.pop(checking_id, None)
            return PaymentResponse(
                ok=False,
                checking_id=checking_id,
                fee_msat=fee_msat,
                error_message=payment_data.get("error") or "Payment failed.",
            )
        return PaymentResponse(ok=None, checking_id=checking_id, fee_msat=fee_msat)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(f"/v1/charge/{checking_id}")
        if r.is_error:
            return PaymentPendingStatus()
        data = r.json()["data"]
        statuses = {"processing": None, "paid": True, "unpaid": None, "expired": False}
        return PaymentStatus(statuses[data.get("status")])

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        provider_id = self.payment_ids.get(checking_id, checking_id)
        r = await self.client.get(f"/v1/withdrawal/{provider_id}")

        if r.is_error:
            return PaymentPendingStatus()

        try:
            data = r.json()["data"]
            statuses = {
                "initial": None,
                "pending": None,
                "confirmed": True,
                "error": False,
                "failed": False,
            }
            fee_msat = -data["fee"] * 1000
            status = PaymentStatus(statuses[data["status"]], fee_msat)
            if status.success or status.failed:
                self.payment_ids.pop(checking_id, None)
            return status
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while settings.lnbits_running:
            value = await self.queue.get()
            yield value
