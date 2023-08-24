import asyncio
import random
from functools import partial, wraps
from typing import AsyncGenerator, Optional

from loguru import logger
from pyln.client import LightningRpc, RpcError

from lnbits import bolt11 as lnbits_bolt11
from lnbits.settings import settings

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
        self.rpc = settings.corelightning_rpc or settings.clightning_rpc
        self.ln = LightningRpc(self.rpc)

        # check if description_hash is supported (from corelightning>=v0.11.0)
        command = self.ln.help("invoice")["help"][0]["command"]  # type: ignore
        self.supports_description_hash = "deschashonly" in command

        # check last payindex so we can listen from that point on
        self.last_pay_index = 0
        invoices: dict = self.ln.listinvoices()  # type: ignore
        for inv in invoices["invoices"][::-1]:
            if "pay_index" in inv:
                self.last_pay_index = inv["pay_index"]
                break

    async def status(self) -> StatusResponse:
        try:
            funds: dict = self.ln.listfunds()  # type: ignore
            return StatusResponse(
                None, sum([int(ch["our_amount_msat"]) for ch in funds["channels"]])
            )
        except RpcError as exc:
            error_message = f"lightningd '{exc.method}' failed with '{exc.error}'."
            return StatusResponse(error_message, 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        label = f"lbl{random.random()}"
        msat: int = int(amount * 1000)
        try:
            if description_hash and not unhashed_description:
                raise Unsupported(
                    "'description_hash' unsupported by CoreLightning, provide"
                    " 'unhashed_description'"
                )
            if unhashed_description and not self.supports_description_hash:
                raise Unsupported("unhashed_description")
            r: dict = self.ln.invoice(  # type: ignore
                msatoshi=msat,
                label=label,
                description=(
                    unhashed_description.decode() if unhashed_description else memo
                ),
                exposeprivatechannels=True,
                deschashonly=(
                    True if unhashed_description else False
                ),  # we can't pass None here
                expiry=kwargs.get("expiry"),
            )

            if r.get("code") and r.get("code") < 0:  # type: ignore
                raise Exception(r.get("message"))

            return InvoiceResponse(True, r["payment_hash"], r["bolt11"], "")
        except RpcError as exc:
            error_message = (
                f"CoreLightning method '{exc.method}' failed with"
                f" '{exc.error.get('message') or exc.error}'."  # type: ignore
            )
            return InvoiceResponse(False, None, None, error_message)
        except Exception as e:
            return InvoiceResponse(False, None, None, str(e))

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        invoice = lnbits_bolt11.decode(bolt11)

        previous_payment = await self.get_payment_status(invoice.payment_hash)
        if previous_payment.paid:
            return PaymentResponse(False, None, None, None, "invoice already paid")

        fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100
        # so fee_limit_percent is applied even on payments with fee < 5000 millisatoshi
        # (which is default value of exemptfee)
        payload = {
            "bolt11": bolt11,
            "maxfeepercent": f"{fee_limit_percent:.11}",
            "exemptfee": 0,
        }
        try:
            wrapped = async_wrap(_pay_invoice)
            r = await wrapped(self.ln, payload)
        except RpcError as exc:
            try:
                error_message = exc.error["attempts"][-1]["fail_reason"]  # type: ignore
            except Exception:
                error_message = (
                    f"CoreLightning method '{exc.method}' failed with"
                    f" '{exc.error.get('message') or exc.error}'."  # type: ignore
                )
            return PaymentResponse(False, None, None, None, error_message)
        except Exception as exc:
            return PaymentResponse(False, None, None, None, str(exc))

        fee_msat = -int(r["amount_sent_msat"] - r["amount_msat"])
        return PaymentResponse(
            True, r["payment_hash"], fee_msat, r["payment_preimage"], None
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r: dict = self.ln.listinvoices(payment_hash=checking_id)  # type: ignore
        except RpcError:
            return PaymentStatus(None)
        if not r["invoices"]:
            return PaymentStatus(None)

        invoice_resp = r["invoices"][-1]

        if invoice_resp["payment_hash"] == checking_id:
            if invoice_resp["status"] == "paid":
                return PaymentStatus(True)
            elif invoice_resp["status"] == "unpaid":
                return PaymentStatus(None)
            elif invoice_resp["status"] == "expired":
                return PaymentStatus(False)
        else:
            logger.warning(f"supplied an invalid checking_id: {checking_id}")
        return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            r: dict = self.ln.listpays(payment_hash=checking_id)  # type: ignore
        except Exception:
            return PaymentStatus(None)
        if "pays" not in r or not r["pays"]:
            return PaymentStatus(None)
        payment_resp = r["pays"][-1]

        if payment_resp["payment_hash"] == checking_id:
            status = payment_resp["status"]
            if status == "complete":
                fee_msat = -int(
                    payment_resp["amount_sent_msat"] - payment_resp["amount_msat"]
                )

                return PaymentStatus(True, fee_msat, payment_resp["preimage"])
            elif status == "failed":
                return PaymentStatus(False)
            else:
                return PaymentStatus(None)
        else:
            logger.warning(f"supplied an invalid checking_id: {checking_id}")
        return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                wrapped = async_wrap(_paid_invoices_stream)
                paid = await wrapped(self.ln, self.last_pay_index)
                self.last_pay_index = paid["pay_index"]
                yield paid["payment_hash"]
            except Exception as exc:
                logger.error(
                    f"lost connection to corelightning invoices stream: '{exc}', "
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)
