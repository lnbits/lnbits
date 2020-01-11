from requests import Response, post

from .base import InvoiceResponse, TxStatus, Wallet


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

    def pay_invoice(self, bolt11: str) -> Response:
        return post(url=f"{self.endpoint}/payinvoice", headers=self.auth_admin, json={"invoice": bolt11})

    def get_invoice_status(self, payment_hash: str, wait: bool = True) -> TxStatus:
        wait = "true" if wait else "false"
        r = post(url=f"{self.endpoint}/invoicestatus/{payment_hash}?wait={wait}", headers=self.auth_invoice)

        if not r.ok or "error" in r.json():
            return TxStatus(r, None)

        data = r.json()

        if "preimage" not in data or not data["preimage"]:
            return TxStatus(r, False)

        return TxStatus(r, True)

    def get_payment_status(self, payment_hash: str) -> TxStatus:
        r = post(url=f"{self.endpoint}/paymentstatus/{payment_hash}", headers=self.auth_invoice)

        if not r.ok or "error" in r.json():
            return TxStatus(r, None)

        return TxStatus(r, {"complete": True, "failed": False, "unknown": None}[r.json().get("status", "unknown")])
