try:
    from pyln.client import LightningRpc, RpcError  # type: ignore
except ImportError:  # pragma: nocover
    LightningRpc = None

import asyncio
import hashlib
import random
import time
from functools import partial, wraps
from os import getenv
from typing import AsyncGenerator, Optional

from loguru import logger

from lnbits import bolt11 as lnbits_bolt11

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Unsupported,
    Wallet,
)


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


class CoreLightningWallet(Wallet):
    def __init__(self):
        if LightningRpc is None:  # pragma: nocover
            raise ImportError(
                "The `pyln-client` library must be installed to use `CoreLightningWallet`."
            )

        self.rpc = getenv("CORELIGHTNING_RPC") or getenv("CLIGHTNING_RPC")
        self.ln = LightningRpc(self.rpc)

        # check if description_hash is supported (from CLN>=v0.11.0)
        self.supports_description_hash = (
            "deschashonly" in self.ln.help("invoice")["help"][0]["command"]
        )

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
        msat: int = int(amount * 1000)
        try:
            if description_hash and not self.supports_description_hash:
                raise Unsupported("description_hash")
            r = self.ln.invoice(
                msatoshi=msat,
                label=label,
                description=description_hash.decode("utf-8")
                if description_hash
                else memo,
                exposeprivatechannels=True,
                deschashonly=True
                if description_hash
                else False,  # we can't pass None here
            )

            if r.get("code") and r.get("code") < 0:
                raise Exception(r.get("message"))

            return InvoiceResponse(True, r["payment_hash"], r["bolt11"], "")
        except RpcError as exc:
            error_message = f"lightningd '{exc.method}' failed with '{exc.error}'."
            logger.error("RPC error:", error_message)
            return InvoiceResponse(False, None, None, error_message)
        except Exception as e:
            logger.error("error:", e)
            return InvoiceResponse(False, None, None, str(e))

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
        except Exception as exc:
            return PaymentResponse(False, None, 0, None, str(exc))

        fee_msat = r["msatoshi_sent"] - r["msatoshi"]
        return PaymentResponse(
            True, r["payment_hash"], fee_msat, r["payment_preimage"], None
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = self.ln.listinvoices(payment_hash=checking_id)
        except:
            return PaymentStatus(None)
        if not r["invoices"]:
            return PaymentStatus(None)
        if r["invoices"][0]["payment_hash"] == checking_id:
            return PaymentStatus(r["invoices"][0]["status"] == "paid")
        raise KeyError("supplied an invalid checking_id")

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = self.ln.call("listpays", {"payment_hash": checking_id})
        except:
            return PaymentStatus(None)
        if not r["pays"]:
            return PaymentStatus(None)
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
            try:
                wrapped = async_wrap(_paid_invoices_stream)
                paid = await wrapped(self.ln, self.last_pay_index)
                self.last_pay_index = paid["pay_index"]
                yield paid["payment_hash"]
            except Exception as exc:
                logger.error(
                    f"lost connection to cln invoices stream: '{exc}', retrying in 5 seconds"
                )
                await asyncio.sleep(5)
