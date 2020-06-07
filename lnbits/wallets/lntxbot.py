from os import getenv
from requests import post
from binascii import hexlify

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LntxbotWallet(Wallet):
    """https://github.com/fiatjaf/lntxbot/blob/master/api.go"""

    def __init__(self):
        endpoint = getenv("LNTXBOT_API_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Authorization": f"Basic {getenv('LNTXBOT_ADMIN_KEY')}"}
        self.auth_invoice = {"Authorization": f"Basic {getenv('LNTXBOT_INVOICE_KEY')}"}

    def create_invoice(self, amount: int, memo: str = "", description_hash: bytes = b"") -> InvoiceResponse:
        r = post(
            url=f"{self.endpoint}/addinvoice",
            headers=self.auth_invoice,
            json={"amt": str(amount), "memo": memo, "description_hash": hexlify(description_hash).decode("ascii")},
        )
        ok, checking_id, payment_request, error_message = r.ok, None, None, None

        if r.ok:
            data = r.json()
            checking_id, payment_request = data["payment_hash"], data["pay_req"]

            if "error" in data and data["error"]:
                ok = False
                error_message = data["message"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(url=f"{self.endpoint}/payinvoice", headers=self.auth_admin, json={"invoice": bolt11})
        ok, checking_id, fee_msat, error_message = r.ok, None, 0, None

        if r.ok:
            data = r.json()

            if "payment_hash" in data:
                checking_id, fee_msat = data["decoded"]["payment_hash"], data["fee_msat"]
            elif "error" in data and data["error"]:
                ok, error_message = False, data["message"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = post(url=f"{self.endpoint}/invoicestatus/{checking_id}?wait=false", headers=self.auth_invoice)

        if not r.ok or "error" in r.json():
            return PaymentStatus(None)

        data = r.json()

        if "preimage" not in data:
            return PaymentStatus(False)

        return PaymentStatus(True)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = post(url=f"{self.endpoint}/paymentstatus/{checking_id}", headers=self.auth_invoice)

        if not r.ok or "error" in r.json():
            return PaymentStatus(None)

        statuses = {"complete": True, "failed": False, "pending": None, "unknown": None}
        return PaymentStatus(statuses[r.json().get("status", "unknown")])
