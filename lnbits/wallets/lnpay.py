from requests import get, post

from .base import InvoiceResponse, PaymentResponse, TxStatus, Wallet


class LNPayWallet(Wallet):
    """https://docs.lnpay.co/"""

    def __init__(self, *, endpoint: str, admin_key: str, invoice_key: str, api_key: str, read_key: str):
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = admin_key
        self.auth_invoice = invoice_key
        self.auth_read = read_key
        self.auth_api = {"X-Api-Key": api_key}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        payment_hash, payment_request = None, None

        r = post(
            url=f"{self.endpoint}/user/wallet/{self.auth_invoice}/invoice",
            headers=self.auth_api,
            json={"num_satoshis": f"{amount}", "memo": memo},
        )

        if r.ok:
            data = r.json()
            payment_hash, payment_request = data["id"], data["payment_request"]

        return InvoiceResponse(r, payment_hash, payment_request)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(
            url=f"{self.endpoint}/user/wallet/{self.auth_admin}/withdraw",
            headers=self.auth_api,
            json={"payment_request": bolt11},
        )

        return PaymentResponse(r, not r.ok)

    def get_invoice_status(self, payment_hash: str) -> TxStatus:
        r = get(url=f"{self.endpoint}/user/lntx/{payment_hash}", headers=self.auth_api)

        if not r.ok:
            return TxStatus(r, None)

        statuses = {0: None, 1: True, -1: False}
        return TxStatus(r, statuses[r.json()["settled"]])

    def get_payment_status(self, payment_hash: str) -> TxStatus:
        r = get(url=f"{self.endpoint}/user/lntx/{payment_hash}", headers=self.auth_api)

        if not r.ok:
            return TxStatus(r, None)

        statuses = {0: None, 1: True, -1: False}
        return TxStatus(r, statuses[r.json()["settled"]])
