import trio  # type: ignore
import json
import httpx
import random
from os import getenv
from typing import Optional, AsyncGenerator

from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
)


class SparkError(Exception):
    pass


class UnknownError(Exception):
    pass


class SparkWallet(Wallet):
    def __init__(self):
        self.url = getenv("SPARK_URL").replace("/rpc", "")
        self.token = getenv("SPARK_TOKEN")

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
                        self.url + "/rpc",
                        headers={"X-Access": self.token},
                        json={"method": key, "params": params},
                        timeout=40,
                    )
            except (OSError, httpx.ConnectError, httpx.RequestError) as exc:
                raise UnknownError("error connecting to spark: " + str(exc))

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

    async def status(self) -> StatusResponse:
        try:
            funds = await self.listfunds()
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse("Couldn't connect to Spark server", 0)
        except (SparkError, UnknownError) as e:
            return StatusResponse(str(e), 0)

        return StatusResponse(
            None,
            sum([ch["channel_sat"] * 1000 for ch in funds["channels"]]),
        )

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        label = "lbs{}".format(random.random())
        checking_id = label

        try:
            if description_hash:
                r = await self.invoicewithdescriptionhash(
                    msatoshi=amount * 1000,
                    label=label,
                    description_hash=description_hash.hex(),
                )
            else:
                r = await self.invoice(
                    msatoshi=amount * 1000,
                    label=label,
                    description=memo or "",
                    exposeprivatechannels=True,
                )
            ok, payment_request, error_message = True, r["bolt11"], ""
        except (SparkError, UnknownError) as e:
            ok, payment_request, error_message = False, None, str(e)

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:
        try:
            r = await self.pay(bolt11)
        except (SparkError, UnknownError) as exc:
            listpays = await self.listpays(bolt11)
            if listpays:
                pays = listpays["pays"]

                if len(pays) == 0:
                    return PaymentResponse(False, None, 0, None, str(exc))

                pay = pays[0]
                payment_hash = pay["payment_hash"]

                if len(pays) > 1:
                    raise SparkError(
                        f"listpays({payment_hash}) returned an unexpected response: {listpays}"
                    )

                if pay["status"] == "failed":
                    return PaymentResponse(False, None, 0, None, str(exc))
                elif pay["status"] == "pending":
                    return PaymentResponse(None, payment_hash, 0, None, None)
                elif pay["status"] == "complete":
                    r = pay
                    r["payment_preimage"] = pay["preimage"]
                    r["msatoshi"] = int(pay["amount_msat"][0:-4])
                    r["msatoshi_sent"] = int(pay["amount_sent_msat"][0:-4])
                    # this may result in an error if it was paid previously
                    # our database won't allow the same payment_hash to be added twice
                    # this is good
                    pass

        fee_msat = r["msatoshi_sent"] - r["msatoshi"]
        preimage = r["payment_preimage"]
        return PaymentResponse(True, r["payment_hash"], fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.listinvoices(label=checking_id)
        except (SparkError, UnknownError):
            return PaymentStatus(None)

        if not r or not r.get("invoices"):
            return PaymentStatus(None)
        if r["invoices"][0]["status"] == "unpaid":
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

        # ask sparko
        try:
            r = await self.listpays(payment_hash=checking_id)
        except (SparkError, UnknownError):
            return PaymentStatus(None)

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
            except (OSError, httpx.ReadError, httpx.ConnectError, httpx.ReadTimeout):
                pass

            print("lost connection to spark /stream, retrying in 5 seconds")
            await trio.sleep(5)
