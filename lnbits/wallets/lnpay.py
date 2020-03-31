from os import getenv
from requests import get, post

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LNPayWallet(Wallet):
    """https://docs.lnpay.co/"""

    def __init__(self):
        endpoint = getenv("LNPAY_API_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = getenv("LNPAY_ADMIN_KEY")
        self.auth_invoice = getenv("LNPAY_INVOICE_KEY")
        self.auth_read = getenv("LNPAY_READ_KEY")
        self.auth_api = {"X-Api-Key": getenv("LNPAY_API_KEY")}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        r = post(
            url=f"{self.endpoint}/user/wallet/{self.auth_invoice}/invoice",
            headers=self.auth_api,
            json={"num_satoshis": f"{amount}", "memo": memo},
        )
        ok, checking_id, payment_request, error_message = r.status_code == 201, None, None, None

        if ok:
            data = r.json()
            checking_id, payment_request = data["id"], data["payment_request"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(
            url=f"{self.endpoint}/user/wallet/{self.auth_admin}/withdraw",
            headers=self.auth_api,
            json={"payment_request": bolt11},
        )
        ok, checking_id, fee_msat, error_message = r.status_code == 201, None, 0, None

        if ok:
            checking_id = r.json()["lnTx"]["id"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return self.get_payment_status(checking_id)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/user/lntx/{checking_id}", headers=self.auth_api)

        if not r.ok:
            return PaymentStatus(None)

        statuses = {0: None, 1: True, -1: False}
        return PaymentStatus(statuses[r.json()["settled"]])
