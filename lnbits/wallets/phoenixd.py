import asyncio
import base64

from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger

from lnbits import bolt11
from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Unsupported,
    Wallet,
)


class PhoenixdWallet(Wallet):
    """https://phoenix.acinq.co/server/api"""

    def __init__(self):
        try:
            if not settings.phoenixd_api_endpoint:
                raise ValueError("cannot initialize PhoenixdWallet: missing phoenixd_api_endpoint")
            if not settings.phoenixd_api_password:
                raise ValueError("cannot initialize PhoenixdWallet: missing phoenixd_api_password")

            self.endpoint = self.normalize_endpoint(settings.phoenixd_api_endpoint)
            logger.info(f'phoenixd_api_password: {settings.phoenixd_api_password}')

            # encodedAuth = base64.b64encode(f":{settings.phoenixd_api_password}".encode())
            # auth = str(encodedAuth, "utf-8")
            # headers = {
            #     "Authorization": f"Basic {auth}",
            #     "User-Agent": settings.user_agent,
            # }
            # logger.info(f'headers: {headers}')

            auth = (':', settings.phoenixd_api_password)
            logger.info(f'auth: {auth}')
            self.client = httpx.AsyncClient(base_url=self.endpoint, auth=(':', settings.phoenixd_api_password))
        except Exception as e:
            logger.warning(f"Error establishing wallet connection: {e}")


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
        # phoenixd returns everything as a str not int
        # balance is returned in msats already in phoenixd
        return StatusResponse(None, data)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        if description_hash or unhashed_description:
            raise Unsupported("description_hash")

        msats_amount = amount * 1000
        data: Dict = {
            "amount": f"{msats_amount}",
            "description": memo,
            "expiresIn": 3600,
            "callbackUrl": "",
            "internalId": "",
        }

        r = await self.client.post(
            "charges",
            json=data,
            timeout=40,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return InvoiceResponse(False, None, None, error_message)

        data = r.json()["data"]
        checking_id = data["id"]  # this is a phoenixd id
        payment_request = data["invoice"]["request"]
        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(
        self, bolt11_invoice: str, fee_limit_msat: int
    ) -> PaymentResponse:
        r = await self.client.post(
            "payments",
            json={
                "invoice": bolt11_invoice,
                "description": "",
                "amount": "",
                "internalId": "",
                "callbackUrl": "",
            },
            timeout=40,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()

        checking_id = bolt11.decode(bolt11_invoice).payment_hash
        fee_msat = -int(data["data"]["fee"])
        preimage = data["data"]["preimage"]

        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

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
        return PaymentStatus(statuses[data.get("status")])

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(f"payments/{checking_id}")
        if r.is_error:
            return PaymentPendingStatus()

        data = r.json()["data"]

        statuses = {
            "initial": None,
            "pending": None,
            "completed": True,
            "error": None,
            "expired": False,
            "failed": False,
        }

        return PaymentStatus(statuses[data.get("status")], fee_msat=None, preimage=None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
