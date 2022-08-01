import asyncio
import json
from os import getenv
from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger
from websocket import create_connection

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class ClicheWallet(Wallet):
    """https://github.com/fiatjaf/cliche"""

    def __init__(self):
        self.endpoint = getenv("CLICHE_ENDPOINT")

    async def status(self) -> StatusResponse:
        try:
            ws = create_connection(self.endpoint)
            ws.send("get-info")
            r = ws.recv()
        except Exception as exc:
            return StatusResponse(
                f"Failed to connect to {self.endpoint} due to: {exc}", 0
            )
        try:
            data = json.loads(r)
        except:
            return StatusResponse(
                f"Failed to connect to {self.endpoint}, got: '{r.text[:200]}...'", 0
            )

        return StatusResponse(None, data["result"]["wallets"][0]["balance"])

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        if description_hash:
            ws = create_connection(self.endpoint)
            ws.send(
                f"create-invoice --msatoshi {amount*1000} --description_hash {description_hash.decode()}"
            )
            r = ws.recv()
        else:
            ws = create_connection(self.endpoint)
            ws.send(f"create-invoice --msatoshi {amount*1000} --description {memo}")
            r = ws.recv()
        data = json.loads(r)
        checking_id = None
        payment_request = None
        error_message = None
        try:
            if data["error"]["message"]:
                logger.error(data["error"]["message"])
                error_message = data["error"]["message"]
                return InvoiceResponse(
                    False, checking_id, payment_request, error_message
                )
        except:
            checking_id, payment_request = (
                data["result"]["payment_hash"],
                data["result"]["invoice"],
            )
        return InvoiceResponse(True, checking_id, payment_request, error_message)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        ws = create_connection(self.endpoint)
        ws.send(f"pay-invoice --invoice {bolt11}")
        r = ws.recv()
        data = json.loads(r)
        checking_id = None
        error_message = None
        try:
            if data["error"]["message"]:
                logger.error(data["error"]["message"])
                error_message = data["error"]["message"]
                return PaymentResponse(False, None, 0, error_message)
        except:
            checking_id = data["result"]["payment_hash"]
        return PaymentResponse(True, checking_id, 0, error_message)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        ws = create_connection(self.endpoint)
        ws.send(f"check-payment --hash {checking_id}")
        r = ws.recv()
        data = json.loads(r)
        try:
            if data["error"]["message"]:
                logger.error(data["error"]["message"])
                return PaymentStatus(None)
        except:
            statuses = {"pending": None, "complete": True, "failed": False}
        return PaymentStatus(statuses[data["result"]["status"]])

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        ws = create_connection(self.endpoint)
        ws.send(f"check-payment --hash {checking_id}")
        r = ws.recv()
        data = json.loads(r)
        try:
            if data["error"]["message"]:
                logger.error(data["error"]["message"])
                return PaymentStatus(None)
        except:
            statuses = {"pending": None, "complete": True, "failed": False}
        return PaymentStatus(statuses[data["result"]["status"]])

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        try:
            ws = await create_connection(self.endpoint)
            while True:
                r = await ws.recv()
                data = json.loads(r)
                try:
                    if data["result"]["status"]:
                        yield data["result"]["payment_hash"]
                except:
                    continue
        except:
            pass
            logger.error("lost connection to cliche's websocket, retrying in 5 seconds")
            await asyncio.sleep(5)
