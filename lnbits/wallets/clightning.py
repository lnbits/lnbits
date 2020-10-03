try:
    from lightning import LightningRpc, RpcError  # type: ignore
except ImportError:  # pragma: nocover
    LightningRpc = None

import asyncio
import random
import json

from os import getenv
from typing import Optional, AsyncGenerator
from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet, Unsupported


class CLightningWallet(Wallet):
    def __init__(self):
        if LightningRpc is None:  # pragma: nocover
            raise ImportError("The `pylightning` library must be installed to use `CLightningWallet`.")

        self.rpc = getenv("CLIGHTNING_RPC")
        self.ln = LightningRpc(self.rpc)

        # check description_hash support (could be provided by a plugin)
        self.supports_description_hash = False
        try:
            answer = self.ln.help("invoicewithdescriptionhash")
            if answer["help"][0]["command"].startswith(
                "invoicewithdescriptionhash msatoshi label description_hash",
            ):
                self.supports_description_hash = True
        except:
            pass

        # check last payindex so we can listen from that point on
        self.last_pay_index = 0
        invoices = self.ln.listinvoices()
        for inv in invoices["invoices"][::-1]:
            if "pay_index" in inv:
                self.last_pay_index = inv["pay_index"]
                break

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        label = "lbl{}".format(random.random())
        msat = amount * 1000

        try:
            if description_hash:
                if not self.supports_description_hash:
                    raise Unsupported("description_hash")

                params = [msat, label, description_hash.hex()]
                r = self.ln.call("invoicewithdescriptionhash", params)
                return InvoiceResponse(True, label, r["bolt11"], "")
            else:
                r = self.ln.invoice(msat, label, memo, exposeprivatechannels=True)
                return InvoiceResponse(True, label, r["bolt11"], "")
        except RpcError as exc:
            error_message = f"lightningd '{exc.method}' failed with '{exc.error}'."
            return InvoiceResponse(False, label, None, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = self.ln.pay(bolt11)
        return PaymentResponse(True, r["payment_hash"], r["msatoshi_sent"] - r["msatoshi"], None)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = self.ln.listinvoices(checking_id)
        if not r["invoices"]:
            return PaymentStatus(False)
        if r["invoices"][0]["label"] == checking_id:
            return PaymentStatus(r["invoices"][0]["status"] == "paid")
        raise KeyError("supplied an invalid checking_id")

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = self.ln.listpays(payment_hash=checking_id)
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
        reader, writer = await asyncio.open_unix_connection(self.rpc)

        i = 0
        while True:
            call = json.dumps(
                {
                    "method": "waitanyinvoice",
                    "id": 0,
                    "params": [self.last_pay_index],
                }
            )

            print(call)
            writer.write(call.encode("ascii"))
            await writer.drain()

            data = await reader.readuntil(b"\n\n")
            print(data)
            paid = json.loads(data.decode("ascii"))

            paid = self.ln.waitanyinvoice(self.last_pay_index)
            self.last_pay_index = paid["pay_index"]
            yield paid["label"]

            i += 1
