import asyncio
import hmac
from http import HTTPStatus
from typing import AsyncGenerator, Optional

import httpx
from fastapi import HTTPException
from loguru import logger

from lnbits.settings import settings

from ..core.models import Payment, PaymentStatus
from .base import InvoiceResponse, PaymentResponse, StatusResponse, Unsupported, Wallet


class OpenNodeWallet(Wallet):
    """https://developers.opennode.com/"""

    def __init__(self):
        endpoint = settings.opennode_api_endpoint
        key = (
            settings.opennode_key
            or settings.opennode_admin_key
            or settings.opennode_invoice_key
        )
        if not endpoint or not key:
            raise Exception("cannot initialize opennode")

        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth = {"Authorization": key}
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.auth)

    async def cleanup(self):
        await self.client.aclose()

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get("/v1/account/balance", timeout=40)
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse(f"Unable to connect to '{self.endpoint}'", 0)

        data = r.json()["data"]
        if r.is_error:
            return StatusResponse(data["message"], 0)

        return StatusResponse(None, data["balance"]["BTC"] * 1000)

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

        r = await self.client.post(
            "/v1/charges",
            json={
                "amount": amount,
                "description": memo or "",
                # "callback_url": url_for("/webhook_listener", _external=True),
            },
            timeout=40,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return InvoiceResponse(False, None, None, error_message)

        data = r.json()["data"]
        checking_id = data["id"]
        payment_request = data["lightning_invoice"]["payreq"]
        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        r = await self.client.post(
            "/v2/withdrawals",
            json={"type": "ln", "address": bolt11},
            timeout=None,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()["data"]
        checking_id = data["id"]
        fee_msat = -data["fee"] * 1000

        if data["status"] != "paid":
            return PaymentResponse(None, checking_id, fee_msat, None, "payment failed")

        return PaymentResponse(True, checking_id, fee_msat, None, None)

    async def get_invoice_status(self, payment: Payment) -> PaymentStatus:
        r = await self.client.get(f"/v1/charge/{payment.checking_id}")
        if r.is_error:
            return PaymentStatus(None)
        data = r.json()["data"]
        statuses = {"processing": None, "paid": True, "unpaid": None}
        return PaymentStatus(statuses[data.get("status")])

    async def get_payment_status(self, payment: Payment) -> PaymentStatus:
        r = await self.client.get(f"/v1/withdrawal/{payment.checking_id}")

        if r.is_error:
            return PaymentStatus(None)

        data = r.json()["data"]
        statuses = {
            "initial": None,
            "pending": None,
            "confirmed": True,
            "error": None,
            "failed": False,
        }
        fee_msat = -data.get("fee") * 1000
        return PaymentStatus(statuses[data.get("status")], fee_msat)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value

    async def webhook_listener(self):
        # TODO: request.form is undefined, was it something with Flask or quart?
        # probably issue introduced when refactoring?
        data = await request.form  # type: ignore
        if "status" not in data or data["status"] != "paid":
            raise HTTPException(status_code=HTTPStatus.NO_CONTENT)

        charge_id = data["id"]
        x = hmac.new(self.auth["Authorization"].encode("ascii"), digestmod="sha256")
        x.update(charge_id.encode("ascii"))
        if x.hexdigest() != data["hashed_order"]:
            logger.error("invalid webhook, not from opennode")
            raise HTTPException(status_code=HTTPStatus.NO_CONTENT)

        await self.queue.put(charge_id)
        raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
