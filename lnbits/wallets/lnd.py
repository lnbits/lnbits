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
            json={"value": f"{amount}", "description_hash": memo},  # , "private": True},
        )

        if r.ok:
            data = r.json()
            payment_hash, payment_request = data["r_hash"], data["payment_request"]

        return InvoiceResponse(r, payment_hash, payment_request)

    def pay_invoice(self, bolt11: str) -> Response:
        raise NotImplementedError

    def get_invoice_status(self, payment_hash: str, wait: bool = True) -> TxStatus:
        r = get(url=f"{self.endpoint}/v1/invoice", headers=self.auth_admin, params={"r_hash": payment_hash})

        if not r.ok:
            return TxStatus(r, None)

        return TxStatus(r, r.json()["settled"])

    def get_payment_status(self, payment_hash: str) -> TxStatus:
        r = get(url=f"{self.endpoint}/v1/payments", headers=self.auth_admin, params={"include_incomplete": True})

        if not r.ok:
            return TxStatus(r, None)

        payments = [p for p in r.json()["payments"] if p["payment_hash"] == payment_hash]
        payment = payments[0] if payments else None

        # check payment.status: https://api.lightning.community/rest/index.html?python#peersynctype
        return TxStatus(r, {0: None, 1: None, 2: True, 3: False}[payment["status"]] if payment else None)
