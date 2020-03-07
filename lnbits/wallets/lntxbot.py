from requests import post

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LntxbotWallet(Wallet):
    """https://github.com/fiatjaf/lntxbot/blob/master/api.go"""

    def __init__(self, *, endpoint: str, admin_key: str, invoice_key: str):
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Authorization": f"Basic {admin_key}"}
        self.auth_invoice = {"Authorization": f"Basic {invoice_key}"}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        payment_hash, payment_request = None, None
        r = post(url=f"{self.endpoint}/addinvoice", headers=self.auth_invoice, json={"amt": str(amount), "memo": memo})

        if r.ok:
            data = r.json()
            payment_hash, payment_request = data["payment_hash"], data["pay_req"]

        return InvoiceResponse(r, payment_hash, payment_request)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(url=f"{self.endpoint}/payinvoice", headers=self.auth_admin, json={"invoice": bolt11})
        failed, fee_msat, error_message = not r.ok, 0, None

        if r.ok:
            data = r.json()
            if "error" in data and data["error"]:
                failed = True
                error_message = data["message"]
            elif "fee_msat" in data:
                fee_msat = data["fee_msat"]

        return PaymentResponse(r, failed, fee_msat, error_message)

    def get_invoice_status(self, payment_hash: str) -> PaymentStatus:
        r = post(url=f"{self.endpoint}/invoicestatus/{payment_hash}?wait=false", headers=self.auth_invoice)

        if not r.ok:
            return PaymentStatus(r, None)

        data = r.json()

        if "error" in data:
            return PaymentStatus(r, None)

        if "preimage" not in data or not data["preimage"]:
            return PaymentStatus(r, False)

        return PaymentStatus(r, True)

    def get_payment_status(self, payment_hash: str) -> PaymentStatus:
        r = post(url=f"{self.endpoint}/paymentstatus/{payment_hash}", headers=self.auth_invoice)

        if not r.ok or "error" in r.json():
            return PaymentStatus(r, None)

        statuses = {"complete": True, "failed": False, "pending": None, "unknown": None}
        return PaymentStatus(r, statuses[r.json().get("status", "unknown")])
