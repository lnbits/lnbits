from requests import get, post
from .base import InvoiceResponse, PaymentResponse, TxStatus, Wallet


class LndWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""

    def __init__(self, *, endpoint: str, admin_macaroon: str, invoice_macaroon: str, read_macaroon: str):
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Grpc-Metadata-macaroon": admin_macaroon}
        self.auth_invoice = {"Grpc-Metadata-macaroon": invoice_macaroon}
        self.auth_read = {"Grpc-Metadata-macaroon": read_macaroon}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        payment_hash, payment_request = None, None
        r = post(
            url=f"{self.endpoint}/v1/invoices",
            headers=self.auth_admin,
            verify=False,
            json={"value": amount, "memo": memo, "private": True},
        )

        if r.ok:
            data = r.json()
            payment_request = data["payment_request"]

        rr = get(url=f"{self.endpoint}/v1/payreq/{payment_request}", headers=self.auth_read, verify=False,)

        if rr.ok:
            dataa = rr.json()
            payment_hash = dataa["payment_hash"]

        return InvoiceResponse(r, payment_hash, payment_request)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(
            url=f"{self.endpoint}/v1/channels/transactions",
            headers=self.auth_admin,
            verify=False,
            json={"payment_request": bolt11},
        )
        return PaymentResponse(r, not r.ok)

    def get_invoice_status(self, payment_hash: str) -> TxStatus:
        r = get(url=f"{self.endpoint}/v1/invoice/{payment_hash}", headers=self.auth_read, verify=False)

        if not r.ok or "settled" not in r.json():
            return TxStatus(r, None)

        return TxStatus(r, r.json()["settled"])

    def get_payment_status(self, payment_hash: str) -> TxStatus:
        r = get(
            url=f"{self.endpoint}/v1/payments",
            headers=self.auth_admin,
            verify=False,
            params={"include_incomplete": True},
        )

        if not r.ok:
            return TxStatus(r, None)

        payments = [p for p in r.json()["payments"] if p["payment_hash"] == payment_hash]
        payment = payments[0] if payments else None

        # check payment.status: https://api.lightning.community/rest/index.html?python#peersynctype
        statuses = {"UNKNOWN": None, "IN_FLIGHT": None, "SUCCEEDED": True, "FAILED": False}
        return TxStatus(r, statuses[payment["status"]] if payment else None)
