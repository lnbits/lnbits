from os import getenv
from requests import get, post

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class OpenNodeWallet(Wallet):
    """https://developers.opennode.com/"""

    def __init__(self):
        endpoint = getenv("OPENNODE_API_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Authorization": getenv("OPENNODE_ADMIN_KEY")}
        self.auth_invoice = {"Authorization": getenv("OPENNODE_INVOICE_KEY")}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        r = post(
            url=f"{self.endpoint}/v1/charges",
            headers=self.auth_invoice,
            json={"amount": f"{amount}", "description": memo},  # , "private": True},
        )
        ok, checking_id, payment_request, error_message = r.ok, None, None, None

        if r.ok:
            data = r.json()["data"]
            checking_id, payment_request = data["id"], data["lightning_invoice"]["payreq"]
        else:
            error_message = r.json()["message"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(url=f"{self.endpoint}/v2/withdrawals", headers=self.auth_admin, json={"type": "ln", "address": bolt11})
        ok, checking_id, fee_msat, error_message = r.ok, None, 0, None

        if r.ok:
            data = r.json()["data"]
            checking_id, fee_msat = data["id"], data["fee"] * 1000
        else:
            error_message = r.json()["message"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/v1/charge/{checking_id}", headers=self.auth_invoice)

        if not r.ok:
            return PaymentStatus(None)

        statuses = {"processing": None, "paid": True, "unpaid": False}
        return PaymentStatus(statuses[r.json()["data"]["status"]])

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/v1/withdrawal/{checking_id}", headers=self.auth_admin)

        if not r.ok:
            return PaymentStatus(None)

        statuses = {"pending": None, "confirmed": True, "error": False, "failed": False}
        return PaymentStatus(statuses[r.json()["data"]["status"]])
