try:
    from lightning import LightningRpc, RpcError  # type: ignore
except ImportError:  # pragma: nocover
    LightningRpc = None

import asyncio
import random
from functools import partial, wraps
from os import getenv
from typing import AsyncGenerator, Optional
import time

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Unsupported,
    Wallet,
)
from lnbits import bolt11 as lnbits_bolt11


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        partial_func = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, partial_func)

    return run


def _pay_invoice(ln, payload):
    return ln.call("pay", payload)


def _paid_invoices_stream(ln, last_pay_index):
    return ln.waitanyinvoice(last_pay_index)


class CLightningWallet(Wallet):
    def __init__(self):
        if LightningRpc is None:  # pragma: nocover
            raise ImportError(
                "The `pylightning` library must be installed to use `CLightningWallet`."
            )

        self.rpc = getenv("CLIGHTNING_RPC")
        self.ln = LightningRpc(self.rpc)

        # check description_hash support (could be provided by a plugin)
        self.supports_description_hash = False
        try:
            answer = self.ln.help("invoicewithdescriptionhash")
            if answer["help"][0]["command"].startswith(
                "invoicewithdescriptionhash msatoshi label description_hash"
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

    async def status(self) -> StatusResponse:
        try:
            funds = self.ln.listfunds()
            return StatusResponse(
                None, sum([ch["channel_sat"] * 1000 for ch in funds["channels"]])
            )
        except RpcError as exc:
            error_message = f"lightningd '{exc.method}' failed with '{exc.error}'."
            return StatusResponse(error_message, 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
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

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        invoice = lnbits_bolt11.decode(bolt11)
        fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100

        payload = {
            "bolt11": bolt11,
            "maxfeepercent": "{:.11}".format(fee_limit_percent),
            "exemptfee": 0,  # so fee_limit_percent is applied even on payments with fee under 5000 millisatoshi (which is default value of exemptfee)
        }
        try:
            wrapped = async_wrap(_pay_invoice)
            r = await wrapped(self.ln, payload)
        except RpcError as exc:
            return PaymentResponse(False, None, 0, None, str(exc))

        fee_msat = r["msatoshi_sent"] - r["msatoshi"]
        preimage = r["payment_preimage"]
        return PaymentResponse(True, r["payment_hash"], fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = self.ln.listinvoices(checking_id)
        if not r["invoices"]:
            return PaymentStatus(False)
        if r["invoices"][0]["label"] == checking_id:
            return PaymentStatus(r["invoices"][0]["status"] == "paid")
        raise KeyError("supplied an invalid checking_id")

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = self.ln.call("listpays", {"payment_hash": checking_id})
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
        while True:
            wrapped = async_wrap(_paid_invoices_stream)
            paid = await wrapped(self.ln, self.last_pay_index)
            self.last_pay_index = paid["pay_index"]
            yield paid["label"]
