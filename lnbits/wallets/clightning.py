try:
    from lightning import LightningRpc  # type: ignore
except ImportError:  # pragma: nocover
    LightningRpc = None

import random

from os import getenv

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet, Unsupported


class CLightningWallet(Wallet):
    def __init__(self):
        if LightningRpc is None:  # pragma: nocover
            raise ImportError("The `pylightning` library must be installed to use `CLightningWallet`.")

        self.l1 = LightningRpc(getenv("CLIGHTNING_RPC"))

    def create_invoice(self, amount: int, memo: str = "", description_hash: bytes = b"") -> InvoiceResponse:
        if description_hash:
            raise Unsupported("description_hash")

        label = "lbl{}".format(random.random())
        r = self.l1.invoice(amount * 1000, label, memo, exposeprivatechannels=True)
        ok, checking_id, payment_request, error_message = True, r["payment_hash"], r["bolt11"], None
        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = self.l1.pay(bolt11)
        ok, checking_id, fee_msat, error_message = True, r["payment_hash"], r["msatoshi_sent"] - r["msatoshi"], None
        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = self.l1.listinvoices(checking_id)
        if not r["invoices"]:
            return PaymentStatus(False)
        if r["invoices"][0]["label"] == checking_id:
            return PaymentStatus(r["pays"][0]["status"] == "paid")
        raise KeyError("supplied an invalid checking_id")

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = self.l1.listpays(payment_hash=checking_id)
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
