import asyncio
import hashlib
from collections.abc import AsyncGenerator

import httpx
from loguru import logger

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
    payment_request_was_rejected,
)


class ZBDWallet(Wallet):
    """https://zbd.dev/api-reference/"""

    def __init__(self):
        if not settings.zbd_api_endpoint:
            raise ValueError("cannot initialize ZBDWallet: missing zbd_api_endpoint")
        if not settings.zbd_api_key:
            raise ValueError("cannot initialize ZBDWallet: missing zbd_api_key")

        self.endpoint = normalize_endpoint(settings.zbd_api_endpoint)
        headers = {
            "apikey": settings.zbd_api_key,
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
            r = await self.client.get("wallet", timeout=10)
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse(f"Unable to connect to '{self.endpoint}'", 0)

        if r.is_error:
            error_message = r.json()["message"]
            return StatusResponse(error_message, 0)

        data = int(r.json()["data"]["balance"])
        # ZBD returns everything as a str not int
        # balance is returned in msats already in ZBD
        return StatusResponse(None, data)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        # https://api.zebedee.io/v0/charges

        msats_amount = amount * 1000
        data: dict = {
            "amount": f"{msats_amount}",
            "expiresIn": 3600,
            "callbackUrl": "",
            "internalId": "",
        }

        ## handle description_hash and unhashed for ZBD
        if description_hash:
            data["description"] = description_hash.hex()
        elif unhashed_description:
            data["description"] = hashlib.sha256(unhashed_description).hexdigest()
        else:
            data["description"] = memo or ""

        r = await self.client.post(
            "charges",
            json=data,
            timeout=40,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return InvoiceResponse(ok=False, error_message=error_message)

        data = r.json()["data"]
        checking_id = data["id"]  # this is a zbd id
        payment_request = data["invoice"]["request"]
        preimage = data["invoice"].get("preimage")
        return InvoiceResponse(
            ok=True,
            checking_id=checking_id,
            payment_request=payment_request,
            preimage=preimage,
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        # https://api.zebedee.io/v0/payments
        try:
            r = await self.client.post(
                "payments",
                json={
                    "invoice": bolt11,
                    "description": "",
                    "amount": "",
                    "internalId": "",
                    "callbackUrl": "",
                },
                timeout=40,
            )
        except Exception as exc:
            logger.warning(exc)
            return PaymentResponse(error_message="Unable to query ZBD.")

        if r.is_error:
            try:
                error_message = r.json().get("message", r.text)
            except Exception:
                error_message = r.text
            return PaymentResponse(
                ok=False if payment_request_was_rejected(r.status_code) else None,
                error_message=error_message,
            )

        try:
            data = r.json()["data"]
            checking_id = data.get("id")
            fee = data.get("fee")
            fee_msat = -int(fee) if fee is not None else None
            preimage = data.get("preimage")
            status = str(data.get("status", "")).lower()
        except Exception as exc:
            logger.warning(exc)
            return PaymentResponse(error_message="Invalid ZBD payment response.")

        if status == "completed":
            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=fee_msat,
                preimage=preimage,
            )
        if status in {"failed", "expired"}:
            return PaymentResponse(
                ok=False,
                checking_id=checking_id,
                fee_msat=fee_msat,
                error_message=data.get("errorMessage"),
            )
        return PaymentResponse(
            ok=None,
            checking_id=checking_id,
            fee_msat=fee_msat,
            error_message=data.get("errorMessage"),
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(f"charges/{checking_id}")
        if r.is_error:
            return PaymentPendingStatus()
        data = r.json()["data"]

        statuses = {
            "pending": None,
            "paid": True,
            "unpaid": None,
            "expired": False,
            "completed": True,
        }
        return PaymentStatus(paid=statuses[data.get("status")])

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.client.get(f"payments/{checking_id}")
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

        if r.is_error:
            return PaymentPendingStatus()

        try:
            data = r.json()["data"]
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

        statuses = {
            "initial": None,
            "pending": None,
            "completed": True,
            "error": None,
            "expired": False,
            "failed": False,
        }
        return PaymentStatus(paid=statuses.get(data.get("status")))

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while settings.lnbits_running:
            value = await self.queue.get()
            yield value
