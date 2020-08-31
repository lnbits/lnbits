from os import getenv
from typing import Optional, Dict
from requests import get, post

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LNbitsWallet(Wallet):
    """https://github.com/lnbits/lnbits"""

    def __init__(self):
        self.endpoint = getenv("LNBITS_ENDPOINT")
        self.auth_admin = {"X-Api-Key": getenv("LNBITS_ADMIN_KEY")}
        self.auth_invoice = {"X-Api-Key": getenv("LNBITS_INVOICE_KEY")}

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        data: Dict = {"out": False, "amount": amount}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        else:
            data["memo"] = memo or ""

        r = post(url=f"{self.endpoint}/api/v1/payments", headers=self.auth_invoice, json=data,)
        ok, checking_id, payment_request, error_message = r.ok, None, None, None

        if r.ok:
            data = r.json()
            checking_id, payment_request = data["checking_id"], data["payment_request"]
        else:
            error_message = r.json()["message"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(url=f"{self.endpoint}/api/v1/payments", headers=self.auth_admin, json={"out": True, "bolt11": bolt11})
        ok, checking_id, fee_msat, error_message = True, None, 0, None

        if r.ok:
            data = r.json()
            checking_id = data["checking_id"]
        else:
            error_message = r.json()["message"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/api/v1/payments/{checking_id}", headers=self.auth_invoice)

        if not r.ok:
            return PaymentStatus(None)

        return PaymentStatus(r.json()["paid"])

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/api/v1/payments/{checking_id}", headers=self.auth_invoice)

        if not r.ok:
            return PaymentStatus(None)

        return PaymentStatus(r.json()["paid"])
