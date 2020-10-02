try:
    from lightning import LightningRpc, RpcError  # type: ignore
except ImportError:  # pragma: nocover
    LightningRpc = None

import random

from os import getenv
from typing import Optional, AsyncGenerator
from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet, Unsupported


class CLightningWallet(Wallet):
    def __init__(self):
        if LightningRpc is None:  # pragma: nocover
            raise ImportError("The `pylightning` library must be installed to use `CLightningWallet`.")

        self.ln = LightningRpc(getenv("CLIGHTNING_RPC"))

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
        if len(invoices["invoices"]):
            self.last_pay_index = invoices["invoices"][-1]["pay_index"]

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        label = "lbl{}".format(random.random())
        msat = amount * 1000

        try:
            if description_hash:
                if not self.supports_description_hash:
                    raise Unsupported("description_hash")

                r = self.ln.call("invoicewithdescriptionhash", [msat, label, memo])
                return InvoiceResponse(True, label, r["bolt11"], "")
            else:
                r = self.ln.invoice(msat, label, memo, exposeprivatechannels=True)
                return InvoiceResponse(True, label, r["bolt11"], "")
        except RpcError as exc:
            error_message = f"lightningd '{exc.method}' failed with '{exc.error}'."
            return InvoiceResponse(False, label, None, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = self.ln.pay(bolt11)
        ok, checking_id, fee_msat, error_message = True, r["payment_hash"], r["msatoshi_sent"] - r["msatoshi"], None
        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = self.ln.listinvoices(checking_id)
        if not r["invoices"]:
            return PaymentStatus(False)
        if r["invoices"][0]["label"] == checking_id:
            return PaymentStatus(r["pays"][0]["status"] == "paid")
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
        while True:
            paid = self.ln.waitanyinvoice(self.last_pay_index)
            self.last_pay_index = paid["pay_index"]
            yield paid["label"]
