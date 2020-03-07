from requests import get, post

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class OpenNodeWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""

    def __init__(self, *, endpoint: str, admin_key: str, invoice_key: str):
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Authorization": admin_key}
        self.auth_invoice = {"Authorization": invoice_key}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        payment_hash, payment_request = None, None
        r = post(
            url=f"{self.endpoint}/v1/charges",
            headers=self.auth_invoice,
            json={"amount": f"{amount}", "description": memo},  # , "private": True},
        )
        if r.ok:
            data = r.json()
            payment_hash, payment_request = data["data"]["id"], data["data"]["lightning_invoice"]["payreq"]

        return InvoiceResponse(r, payment_hash, payment_request)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(url=f"{self.endpoint}/v2/withdrawals", headers=self.auth_admin, json={"type": "ln", "address": bolt11})
        return PaymentResponse(r, not r.ok)

    def get_invoice_status(self, payment_hash: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/v1/charge/{payment_hash}", headers=self.auth_invoice)

        if not r.ok:
            return PaymentStatus(r, None)

        statuses = {"processing": None, "paid": True, "unpaid": False}
        return PaymentStatus(r, statuses[r.json()["data"]["status"]])

    def get_payment_status(self, payment_hash: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/v1/withdrawal/{payment_hash}", headers=self.auth_admin)

        if not r.ok:
            return PaymentStatus(r, None)

        statuses = {"pending": None, "confirmed": True, "error": False, "failed": False}
        return PaymentStatus(r, statuses[r.json()["data"]["status"]])
