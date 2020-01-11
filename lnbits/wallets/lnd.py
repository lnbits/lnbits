from requests import Response, get, post

from .base import InvoiceResponse, TxStatus, Wallet


class LndWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""

    def __init__(self, *, endpoint: str, admin_macaroon: str):
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Grpc-Metadata-macaroon": admin_macaroon}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        payment_hash, payment_request = None, None
        r = post(
            url=f"{self.endpoint}/v1/invoices",
            headers=self.auth_admin,
            json={"value": f"{amount}", "description_hash": memo, "private": True},
        )

        if r.ok:
            payment_request = r.json()["payment_request"]
            decoded = get(url=f"{self.endpoint}/v1/payreq/{payment_request}", headers=self.auth_admin)
            payment_hash, payment_request = decoded.json()["payment_hash"], payment_request

        return InvoiceResponse(r, payment_hash, payment_request)

    def pay_invoice(self, bolt11: str) -> Response:
        return post(
            url=f"{self.endpoint}/v1/channels/transactions", headers=self.auth_admin, json={"payment_request": bolt11}
        )

    def get_invoice_status(self, payment_hash: str, wait: bool = True) -> TxStatus:
        r = get(url=f"{self.endpoint}/v1/invoice/{payment_hash}", headers=self.auth_admin)

        if not r.ok or "settled" not in r.json():
            return TxStatus(r, None)

        return TxStatus(r, r.json()["settled"])

    def get_payment_status(self, payment_hash: str) -> TxStatus:
        r = get(url=f"{self.endpoint}/v1/payments", headers=self.auth_admin, params={"include_incomplete": True})

        if not r.ok:
            return TxStatus(r, None)

        payments = [p for p in r.json()["payments"] if p["payment_hash"] == payment_hash]
        payment = payments[0] if payments else None

        # check payment.status: https://api.lightning.community/rest/index.html?python#peersynctype
        statuses = {"UNKNOWN": None, "IN_FLIGHT": None, "SUCCEEDED": True, "FAILED": False}
        return TxStatus(r, statuses[payment["status"]] if payment else None)
