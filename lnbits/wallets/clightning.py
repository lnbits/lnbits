try:
    from lightning import LightningRpc  # type: ignore
except ImportError:  # pragma: nocover
    LightningRpc = None

import random

from os import getenv

from .base import InvoiceResponse, PaymentStatus, PaymentResponse, Wallet


class CLightningWallet(Wallet):

    def __init__(self):
        if LightningRpc is None:  # pragma: nocover
            raise ImportError("The `pylightning` library must be installed to use `CLightningWallet`.")

        self.l1 = LightningRpc(getenv("CLIGHTNING_RPC"))

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        label = "lbl{}".format(random.random())
        r = self.l1.invoice(amount*1000, label, memo, exposeprivatechannels=True)
        ok, checking_id, payment_request, error_message = True, r["payment_hash"], r["bolt11"], None
        return InvoiceResponse(ok, label, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = self.l1.pay(bolt11)
        ok, checking_id, fee_msat, error_message = True, None, 0, None
        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = self.l1.listinvoices(checking_id)
        if r['invoices'][0]['status'] == 'unpaid':
            return PaymentStatus(False)
        return PaymentStatus(True)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = self.l1.listsendpays(checking_id)
        if not r.ok:
            return PaymentStatus(None)
        payments = [p for p in r.json()["payments"] if p["payment_hash"] == checking_id]
        payment = payments[0] if payments else None
        statuses = {"UNKNOWN": None, "IN_FLIGHT": None, "SUCCEEDED": True, "FAILED": False}
        return PaymentStatus(statuses[payment["status"]] if payment else None)

    # Should be used with websocket only.
    def wait_invoice(self, checking_id: str) -> PaymentStatus:
        r = self.l1.waitinvoice(checking_id)
        return PaymentStatus(r["status"] == "paid")
