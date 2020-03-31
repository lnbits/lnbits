from os import getenv
from requests import get, post

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LndWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""

    def __init__(self):
        endpoint = getenv("LND_API_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Grpc-Metadata-macaroon": getenv("LND_ADMIN_MACAROON")}
        self.auth_invoice = {"Grpc-Metadata-macaroon": getenv("LND_INVOICE_MACAROON")}
        self.auth_read = {"Grpc-Metadata-macaroon": getenv("LND_READ_MACAROON")}

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        r = post(
            url=f"{self.endpoint}/v1/invoices",
            headers=self.auth_admin,
            verify=False,
            json={"value": amount, "memo": memo, "private": True},
        )
        ok, checking_id, payment_request, error_message = r.ok, None, None, None

        if r.ok:
            data = r.json()
            payment_request = data["payment_request"]

            rr = get(url=f"{self.endpoint}/v1/payreq/{payment_request}", headers=self.auth_read, verify=False)

            if rr.ok:
                checking_id = rr.json()["payment_hash"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(
            url=f"{self.endpoint}/v1/channels/transactions",
            headers=self.auth_admin,
            verify=False,
            json={"payment_request": bolt11},
        )
        ok, checking_id, fee_msat, error_message = r.ok, None, 0, None
        data = r.json()["data"]

        if "payment_error" in data and data["payment_error"]:
            ok, error_message = False, data["payment_error"]
        else:
            checking_id = data["payment_hash"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/v1/invoice/{checking_id}", headers=self.auth_read, verify=False)

        if not r.ok or "settled" not in r.json():
            return PaymentStatus(None)

        return PaymentStatus(r.json()["settled"])

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = get(
            url=f"{self.endpoint}/v1/payments",
            headers=self.auth_admin,
            verify=False,
            params={"include_incomplete": True},
        )

        if not r.ok:
            return PaymentStatus(None)

        payments = [p for p in r.json()["payments"] if p["payment_hash"] == checking_id]
        payment = payments[0] if payments else None

        # check payment.status: https://api.lightning.community/rest/index.html?python#peersynctype
        statuses = {"UNKNOWN": None, "IN_FLIGHT": None, "SUCCEEDED": True, "FAILED": False}
        return PaymentStatus(statuses[payment["status"]] if payment else None)
