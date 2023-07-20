import asyncio
import json
import random
from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger

from lnbits import bolt11 as lnbits_bolt11
from lnbits.settings import settings

from ..core.models import Payment, PaymentStatus
from .base import InvoiceResponse, PaymentResponse, StatusResponse, Wallet


class CLNRestWallet(Wallet):
    def __init__(self):
        url = settings.cln_rest_url
        macaroon = settings.cln_rest_macaroon
        if not url or not macaroon:
            raise Exception("cannot initialize CLN-rest")

        # check if macaroon is base64 or hex
        macaroon_ishex = True
        try:
            bytes.fromhex(macaroon)
        except ValueError:
            macaroon_ishex = False

        self.url = url[:-1] if url.endswith("/") else url
        self.auth = {
            "macaroon": macaroon,
            "accept": "application/json",
        }
        if macaroon_ishex:
            self.auth["encodingtype"] = "hex"

        self.cert = settings.cln_rest_cert or False
        self.client = httpx.AsyncClient(verify=self.cert, headers=self.auth)
        self.last_pay_index = 0
        self.statuses = {
            "complete": True,
            "failed": False,
            "pending": None,
        }

    async def cleanup(self):
        try:
            await self.client.aclose()
        except Exception as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        r = await self.client.get(f"{self.url}/v1/getBalance", timeout=5)
        try:
            data = r.json()
        except:
            return StatusResponse(
                f"Failed to connect to {self.url}, got: '{r.text[:200]}...'", 0
            )

        if r.is_error:
            return StatusResponse(data.get("error") or "undefined error", 0)
        if len(data) == 0:
            return StatusResponse("no data", 0)

        return StatusResponse(None, int(data.get("totalBalance") * 1000))

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        label = f"lbl{random.random()}"
        data: Dict = {
            "amount": amount * 1000,
            "description": memo,
            "label": label,
        }
        if kwargs.get("expiry"):
            data["expiry"] = kwargs["expiry"]

        if kwargs.get("preimage"):
            data["preimage"] = kwargs["preimage"]

        r = await self.client.post(
            f"{self.url}/v1/invoice/genInvoice",
            data=data,
            timeout=40,
        )

        # TODO: handle errors correctly
        if r.is_error:
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text

            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        assert "payment_hash" in data
        assert "bolt11" in data
        # NOTE: use payment_hash when cln-rest updates and supports it
        # return InvoiceResponse(True, data["payment_hash"], data["bolt11"], None)
        return InvoiceResponse(True, label, data["bolt11"], None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        invoice = lnbits_bolt11.decode(bolt11)
        fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100
        r = await self.client.post(
            f"{self.url}/v1/pay",
            data={
                "invoice": bolt11,
                "maxfeepercent": f"{fee_limit_percent:.11}",
                "exemptfee": 0,  # so fee_limit_percent is applied even on payments
                # with fee < 5000 millisatoshi (which is default value of exemptfee)
            },
            timeout=None,
        )

        # TODO: handle errors correctly
        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()

        if data["status"] != "complete":
            return PaymentResponse(False, None, None, None, "payment failed")

        checking_id = data["payment_hash"]
        preimage = data["payment_preimage"]
        fee_msat = data["msatoshi_sent"] - data["msatoshi"]

        return PaymentResponse(
            self.statuses.get(data["status"]), checking_id, fee_msat, preimage, None
        )

    async def get_invoice_status(self, payment: Payment) -> PaymentStatus:
        # get invoice bolt11 from checking_id
        # cln-rest wants the "label" here....
        # NOTE: We can get rid of all labels and use payment_hash when cln-rest updates and supports it
        r = await self.client.get(
            f"{self.url}/v1/invoice/listInvoices",
            params={"label": payment.checking_id},
        )
        try:
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or data.get("invoices") is None:
                raise Exception("error in eclair response")
            return PaymentStatus(self.statuses.get(data["invoices"][0]["status"]))
        except:
            return PaymentStatus(None)

    async def get_payment_status(self, payment: Payment) -> PaymentStatus:
        # cln-rest wants the "bolt11" here.... sigh
        r = await self.client.get(
            f"{self.url}/v1/pay/listPays",
            params={"invoice": payment.bolt11},
        )
        try:
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or not data.get("pays"):
                raise Exception("error in cln-rest response")

            pay = data["pays"][0]

            fee_msat, preimage = None, None
            if self.statuses[pay["status"]]:
                # cut off "msat" and convert to int
                fee_msat = -int(pay["amount_sent_msat"][:-4]) - int(
                    pay["amount_msat"][:-4]
                )
                preimage = pay["preimage"]

            return PaymentStatus(self.statuses.get(pay["status"]), fee_msat, preimage)
        except:
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                url = f"{self.url}/v1/invoice/waitAnyInvoice/{self.last_pay_index}"
                async with self.client.stream("GET", url, timeout=None) as r:
                    async for line in r.aiter_lines():
                        print(line)
                        try:
                            inv = json.loads(line)
                            paid = inv["status"] == "paid"
                            self.last_pay_index = inv["pay_index"]
                            if not paid:
                                continue
                        except:
                            continue

                        # payment_hash = inv["payment_hash"]
                        # yield payment_hash
                        # NOTE: use payment_hash when cln-rest updates and supports it
                        yield inv["label"]
            except Exception as exc:
                logger.error(
                    f"lost connection to lnd invoices stream: '{exc}', retrying in 5 seconds"
                )
                await asyncio.sleep(5)
