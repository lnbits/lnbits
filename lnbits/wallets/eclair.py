import asyncio
import base64
import json
import urllib.parse
from os import getenv
from typing import AsyncGenerator, Dict, Optional

import httpx
from websockets import connect
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class EclairError(Exception):
    pass


class UnknownError(Exception):
    pass

class EclairWallet(Wallet):
    def __init__(self):
        url = getenv("ECLAIR_URL")
        self.url = url[:-1] if url.endswith("/") else url

        self.ws_url = f"ws://{urllib.parse.urlsplit(self.url).netloc}/ws"

        passw = getenv("ECLAIR_PASS")
        encodedAuth = base64.b64encode(f":{passw}".encode("utf-8"))
        auth = str(encodedAuth, "utf-8")
        self.auth = {"Authorization": f"Basic {auth}"}


    async def status(self) -> StatusResponse:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/usablebalances",
                headers=self.auth,
                timeout=40
            )
        try:
            data = r.json()
        except:
            return StatusResponse(
                f"Failed to connect to {self.url}, got: '{r.text[:200]}...'", 0
            )
        
        if r.is_error:
            return StatusResponse(data["error"], 0)

        return StatusResponse(None, data[0]["canSend"] * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:

        data: Dict = {"amountMsat": amount * 1000}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        else:
            data["description"] = memo or ""

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/createinvoice",
                headers=self.auth,
                data=data,
                timeout=40
            )

        if r.is_error:
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text
                pass

            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        return InvoiceResponse(True, data["paymentHash"], data["serialized"], None)


    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/payinvoice",
                headers=self.auth,
                data={"invoice": bolt11, "blocking": True},
                timeout=40,
            )

        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text
                pass
            return PaymentResponse(False, None, 0, None, error_message)
        
        data = r.json()

        
        checking_id = data["paymentHash"]
        preimage = data["paymentPreimage"]

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/getsentinfo",
                headers=self.auth,
                data={"paymentHash": checking_id},
                timeout=40,
            )

        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text
                pass
            return PaymentResponse(True, checking_id, 0, preimage, error_message) ## ?? is this ok ??

        data = r.json()
        fees = [i["status"] for i in data]
        fee_msat = sum([i["feesPaid"] for i in fees])
        
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)
        


    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/getreceivedinfo",
                headers=self.auth,
                data={"paymentHash": checking_id}
            )
        data = r.json()

        if r.is_error or "error" in data:
            return PaymentStatus(None)

        if data["status"]["type"] != "received":
            return PaymentStatus(False)

        return PaymentStatus(True)           

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url=f"{self.url}/getsentinfo",
                headers=self.auth,
                data={"paymentHash": checking_id}

            )

        data = r.json()[0]

        if r.is_error:
            return PaymentStatus(None)
        
        if data["status"]["type"] != "sent":
            return PaymentStatus(False)

        return PaymentStatus(True)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        
        try:
            async with connect(self.ws_url, extra_headers=[('Authorization', self.auth["Authorization"])]) as ws:
                while True:
                    message = await ws.recv()
                    message = json.loads(message)

                    if message and message["type"] == "payment-received":
                        yield message["paymentHash"]

        except (OSError, ConnectionClosedOK, ConnectionClosedError, ConnectionClosed) as ose:
            print('OSE', ose)
            pass

            print("lost connection to eclair's websocket, retrying in 5 seconds")
            await asyncio.sleep(5)
