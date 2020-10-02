import json
import asyncio
import hmac
import httpx
from http import HTTPStatus
from os import getenv
from typing import Optional, AsyncGenerator
from quart import request, url_for

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet, Unsupported


class OpenNodeWallet(Wallet):
    """https://developers.opennode.com/"""

    def __init__(self):
        endpoint = getenv("OPENNODE_API_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Authorization": getenv("OPENNODE_ADMIN_KEY")}
        self.auth_invoice = {"Authorization": getenv("OPENNODE_INVOICE_KEY")}

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        if description_hash:
            raise Unsupported("description_hash")

        r = httpx.post(
            f"{self.endpoint}/v1/charges",
            headers=self.auth_invoice,
            json={
                "amount": amount,
                "description": memo or "",
                "callback_url": url_for("webhook_listener", _external=True),
            },
        )

        if r.is_error:
            error_message = r.json()["message"]
            return InvoiceResponse(False, None, None, error_message)

        data = r.json()["data"]
        checking_id = data["id"]
        payment_request = data["lightning_invoice"]["payreq"]
        return InvoiceResponse(True, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = httpx.post(
            f"{self.endpoint}/v2/withdrawals", headers=self.auth_admin, json={"type": "ln", "address": bolt11}
        )

        if r.is_error:
            error_message = r.json()["message"]
            return PaymentResponse(False, None, 0, error_message)

        data = r.json()["data"]
        checking_id, fee_msat = data["id"]
        fee_msat = data["fee"] * 1000
        return PaymentResponse(True, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = httpx.get(f"{self.endpoint}/v1/charge/{checking_id}", headers=self.auth_invoice)

        if r.is_error:
            return PaymentStatus(None)

        statuses = {"processing": None, "paid": True, "unpaid": False}
        return PaymentStatus(statuses[r.json()["data"]["status"]])

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = httpx.get(f"{self.endpoint}/v1/withdrawal/{checking_id}", headers=self.auth_admin)

        if r.is_error:
            return PaymentStatus(None)

        statuses = {"initial": None, "pending": None, "confirmed": True, "error": False, "failed": False}
        return PaymentStatus(statuses[r.json()["data"]["status"]])

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue()
        while True:
            yield await self.queue.get()
            self.queue.task_done()

    async def webhook_listener(self):
        print("a request!")
        text: str = await request.get_data()
        print("text", text)
        data = json.loads(text)
        if type(data) is not dict or "event" not in data or data["event"].get("name") != "wallet_receive":
            return "", HTTPStatus.NO_CONTENT

        charge_id = data["id"]
        if data["status"] != "paid":
            return "", HTTPStatus.NO_CONTENT

        x = hmac.new(self.auth_invoice["Authorization"], digestmod="sha256")
        x.update(charge_id)
        if x.hexdigest() != data["hashed_order"]:
            print("invalid webhook, not from opennode")
            return "", HTTPStatus.NO_CONTENT

        self.queue.put_nowait(charge_id)
        return "", HTTPStatus.NO_CONTENT
