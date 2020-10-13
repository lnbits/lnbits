import trio  # type: ignore
import random
import json
import httpx
from os import getenv
from typing import Optional, AsyncGenerator

from .base import StatusResponse, InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class SparkError(Exception):
    pass


class UnknownError(Exception):
    pass


class SparkWallet(Wallet):
    def __init__(self):
        self.url = getenv("SPARK_URL").replace("/rpc", "")
        self.token = getenv("SPARK_TOKEN")

    def __getattr__(self, key):
        def call(*args, **kwargs):
            if args and kwargs:
                raise TypeError(f"must supply either named arguments or a list of arguments, not both: {args} {kwargs}")
            elif args:
                params = args
            elif kwargs:
                params = kwargs
            else:
                params = {}

            r = httpx.post(
                self.url + "/rpc",
                headers={"X-Access": self.token},
                json={"method": key, "params": params},
                timeout=40,
            )
            try:
                data = r.json()
            except:
                raise UnknownError(r.text)

            if r.is_error:
                if r.status_code == 401:
                    raise SparkError("Access key invalid!")

                raise SparkError(data["message"])

            return data

        return call

    def status(self) -> StatusResponse:
        try:
            funds = self.listfunds()
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse("Couldn't connect to Spark server", 0)
        except (SparkError, UnknownError) as e:
            return StatusResponse(str(e), 0)

        return StatusResponse(
            None,
            sum([ch["channel_sat"] * 1000 for ch in funds["channels"]]),
        )

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        label = "lbs{}".format(random.random())
        checking_id = label

        try:
            if description_hash:
                r = self.invoicewithdescriptionhash(
                    msatoshi=amount * 1000,
                    label=label,
                    description_hash=description_hash.hex(),
                )
            else:
                r = self.invoice(
                    msatoshi=amount * 1000, label=label, description=memo or "", exposeprivatechannels=True
                )
            ok, payment_request, error_message = True, r["bolt11"], ""
        except (SparkError, UnknownError) as e:
            ok, payment_request, error_message = False, None, str(e)

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        try:
            r = self.pay(bolt11)
        except (SparkError, UnknownError) as exc:
            return PaymentResponse(False, None, 0, None, str(exc))

        fee_msat = r["msatoshi_sent"] - r["msatoshi"]
        preimage = r["payment_preimage"]
        return PaymentResponse(True, r["payment_hash"], fee_msat, preimage, None)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = self.listinvoices(label=checking_id)
        if not r or not r.get("invoices"):
            return PaymentStatus(None)
        if r["invoices"][0]["status"] == "unpaid":
            return PaymentStatus(False)
        return PaymentStatus(True)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = self.listpays(payment_hash=checking_id)
        if not r["pays"]:
            return PaymentStatus(False)
        if r["pays"][0]["payment_hash"] == checking_id:
            status = r["pays"][0]["status"]
            if status == "complete":
                return PaymentStatus(True)
            elif status == "failed":
                return PaymentStatus(False)
            return PaymentStatus(None)
        raise KeyError("supplied an invalid checking_id")

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        url = self.url + "/stream?access-key=" + self.token

        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", url) as r:
                        async for line in r.aiter_lines():
                            if line.startswith("data:"):
                                data = json.loads(line[5:])
                                if "pay_index" in data and data.get("status") == "paid":
                                    yield data["label"]
            except (OSError, httpx.ReadError):
                pass

            print("lost connection to spark /stream, retrying in 5 seconds")
            await trio.sleep(5)
