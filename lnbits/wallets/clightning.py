from requests import get, post
from os import getenv
from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet
from lightning import LightningRpc
import random

class CLightningWallet(Wallet):

    def __init__(self):
        l1 = LightningRpc(getenv("OPENNODE_API_ENDPOINT"))

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        label = "lbl{}".format(random.random())  
        r = l1.invoice(amount*1000, label, memo, exposeprivatechannels=True)
        print(r)
        ok, checking_id, payment_request, error_message = True, r["payment_hash"], r["bolt11"], None
        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = l1.pay(bolt11)
        ok, checking_id, fee_msat, error_message = True, None, None, None
        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = l1.listinvoices(checking_id)
        if r['invoices'][0]['status'] == 'unpaid':
            return PaymentStatus(False)
        return PaymentStatus(True)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = l1.listsendpays(checking_id)
        if not r.ok:
            return PaymentStatus(r, None)
        payments = [p for p in r.json()["payments"] if p["payment_hash"] == payment_hash]
        payment = payments[0] if payments else None
        statuses = {"UNKNOWN": None, "IN_FLIGHT": None, "SUCCEEDED": True, "FAILED": False}
        return PaymentStatus(statuses[payment["status"]] if payment else None)
