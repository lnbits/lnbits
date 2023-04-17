import asyncio
import hashlib
import json
from asyncio import Future
from typing import AsyncGenerator, Optional

from loguru import logger
from websocket import WebSocketApp
from websockets.client import connect

from lnbits.settings import settings

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
        self.endpoint = settings.cliche_endpoint
        if not self.endpoint:
            raise Exception("cannot initialize cliche")
        self.next_id = 0
        self.futures = {}
        self.ws: WebSocketApp = None

    async def connect(self):
        self.ws = WebSocketApp(
            self.endpoint,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

    async def send_command(self, method: str, params: Optional[dict] = None):
        self.next_id += 1
        command = {"id": self.next_id, "method": method}
        if params is not None:
            command["params"] = params

        self.ws.send(json.dumps(command))
        future = Future()
        self.futures[self.next_id] = future
        data = await future
        return data

    async def status(self) -> StatusResponse:
        r = await self.send_command(method="get-info")

        try:
            data = json.loads(r)
        except Exception:
            return StatusResponse(
                f"Failed to connect to {self.endpoint}, got: '{r[:200]}...'", 0
            )

        return StatusResponse(None, data["result"]["wallets"][0]["balance"])

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        if unhashed_description or description_hash:
            description_hash_str = (
                description_hash.hex()
                if description_hash
                else (
                    hashlib.sha256(unhashed_description).hexdigest()
                    if unhashed_description
                    else None
                )
            )

            r = await self.send_command(
                method="create-invoice",
                params={
                    "msatoshi": amount * 1000,
                    "description_hash": description_hash_str,
                },
            )
        else:

            r = await self.send_command(
                method="create-invoice",
                params={"msatoshi": amount * 1000, "description": memo},
            )

        data = json.loads(r)
        checking_id = None
        payment_request = None
        error_message = None

        if data.get("error") is not None and data["error"].get("message"):
            logger.error(data["error"]["message"])
            error_message = data["error"]["message"]
            return InvoiceResponse(False, checking_id, payment_request, error_message)

        if data.get("result") is not None:
            checking_id, payment_request = (
                data["result"]["payment_hash"],
                data["result"]["invoice"],
            )
        else:
            return InvoiceResponse(False, None, None, "Could not get payment hash")

        return InvoiceResponse(True, checking_id, payment_request, error_message)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:

        checking_id, fee_msat, preimage, error_message, payment_ok = (
            None,
            None,
            None,
            None,
            None,
        )
        for _ in range(2):
            r = await self.send_command(
                method="pay-invoice", params={"invoice": bolt11}
            )
            data = json.loads(r)
            checking_id, fee_msat, preimage, error_message, payment_ok = (
                None,
                None,
                None,
                None,
                None,
            )

            if data.get("error") is not None:
                error_message = data["error"].get("message")
                return PaymentResponse(False, None, None, None, error_message)

            if data.get("method") == "payment_succeeded":
                payment_ok = True
                checking_id = data["params"]["payment_hash"]
                fee_msat = data["params"]["fee_msatoshi"]
                preimage = data["params"]["preimage"]
                continue

            if data.get("result") is None:
                return PaymentResponse(None)

        return PaymentResponse(
            payment_ok, checking_id, fee_msat, preimage, error_message
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = await self.send_command(
            method="check-payment", params={"hash": checking_id}
        )
        data = json.loads(r)

        if data.get("error") is not None and data["error"].get("message"):
            logger.error(data["error"]["message"])
            return PaymentStatus(None)

        statuses = {"pending": None, "complete": True, "failed": False}
        return PaymentStatus(statuses[data["result"]["status"]])

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:

        r = await self.send_command(
            method="check-payment", params={"hash": checking_id}
        )
        data = json.loads(r)

        if data.get("error") is not None and data["error"].get("message"):
            logger.error(data["error"]["message"])
            return PaymentStatus(None)
        payment = data["result"]
        statuses = {"pending": None, "complete": True, "failed": False}
        return PaymentStatus(
            statuses[payment["status"]],
            payment.get("fee_msatoshi"),
            payment.get("preimage"),
        )

    async def on_message(self, message: str):
        try:
            data = json.loads(message)
            msg_id = data.get("id")
            if msg_id is not None and msg_id in self.futures:
                future = self.futures.pop(msg_id)
                future.set_result(data)
            elif data.get("result", {}).get("status"):
                yield data["result"]["payment_hash"]
            else:
                logger.debug(f"Got message: {data}")
        except Exception as exc:
            logger.exception(f"Error processing message: {exc}")
    
    def on_error(self, error):
        logger.warning(f"Error from websocket: {error}")
    
    def on_close(self):
        logger.error("Websocket closed")
        self.ws.close()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                await self.connect()

            except Exception as exc:
                logger.error(
                    f"lost connection to cliche's invoices stream: '{exc}', retrying in"
                    " 5 seconds"
                )
                await asyncio.sleep(5)
                continue
