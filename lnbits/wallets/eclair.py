import trio
import json
import httpx
import random
import base64
import urllib.parse
from os import getenv
from typing import Optional, AsyncGenerator
from trio_websocket import open_websocket_url

from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
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

        passw = getenv("ECLAIR_PASS")
        encodedAuth = base64.b64encode(f":{passw}".encode("utf-8"))
        auth = str(encodedAuth, "utf-8")
        self.auth = {"Authorization": f"Basic {auth}"}

    def __getattr__(self, key):
        async def call(*args, **kwargs):
            if args and kwargs:
                raise TypeError(
                    f"must supply either named arguments or a list of arguments, not both: {args} {kwargs}"
                )
            elif args:
                params = args
            elif kwargs:
                params = kwargs
            else:
                params = {}

            try:
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        self.url + "/" + key,
                        headers=self.auth,
                        data=params,
                        timeout=40,
                    )
            except (OSError, httpx.ConnectError, httpx.RequestError) as exc:
                raise UnknownError("error connecting to eclair: " + str(exc))

            try:
                data = r.json()
                if "error" in data:
                    print('ERROR', data["error"])
                    raise EclairError(data["error"])
            except:
                raise UnknownError(r.text)

            #if r.error:
                # print('ERROR', r)
                # if r.status_code == 401:
                #     raise EclairError("Access key invalid!")

                #raise EclairError(data.error)
            return data

        return call

    async def status(self) -> StatusResponse:
        try:
            funds = await self.usablebalances()
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse("Couldn't connect to Eclair server", 0)
        except (EclairError, UnknownError) as e:
            return StatusResponse(str(e), 0)
        if not funds:
            return StatusResponse("Funding wallet has no funds", 0)

        return StatusResponse(
            None,
            funds[0]["canSend"] * 1000,
        )

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        if description_hash:
            raise Unsupported("description_hash")

        try:
            r = await self.createinvoice(
                    amountMsat=amount * 1000,
                    description=memo or "",
                    exposeprivatechannels=True,
                )
            ok, checking_id, payment_request, error_message = True, r["paymentHash"], r["serialized"], ""
        except (EclairError, UnknownError) as e:
            ok, payment_request, error_message = False, None, str(e)

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:
        try:
            r = await self.payinvoice(invoice=bolt11, blocking=True)
        except (EclairError, UnknownError) as exc:
            return PaymentResponse(False, None, 0, None, str(exc))

        preimage = r["paymentPreimage"]
        return PaymentResponse(True, r["paymentHash"], 0, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.getreceivedinfo(paymentHash=checking_id)

        except (EclairError, UnknownError):
            return PaymentStatus(None)

        if r["status"]["type"] != "received":
            return PaymentStatus(False)
        return PaymentStatus(True)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        # check if it's 32 bytes hex
        if len(checking_id) != 64:
            return PaymentStatus(None)
        try:
            int(checking_id, 16)
        except ValueError:
            return PaymentStatus(None)

        try:
            r = await self.getsentinfo(paymentHash=checking_id)
        except (EclairError, UnknownError):
            return PaymentStatus(None)

        raise KeyError("supplied an invalid checking_id")

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        url = urllib.parse.urlsplit(self.url)
        ws_url = f"ws://{url.netloc}/ws"

        try:
            async with open_websocket_url(ws_url, extra_headers=[('Authorization', self.auth["Authorization"])]) as ws:
                message = await ws.get_message()
                if message["type"] == "payment-received":
                    print('Received message: %s' % message)
                    yield message["paymentHash"]

        except OSError as ose:
            pass

        print("lost connection to eclair's websocket, retrying in 5 seconds")
        await trio.sleep(5)
