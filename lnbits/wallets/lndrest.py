from os import getenv, path
from requests import get, post

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


def macaroon_to_hex(macaroon_path: str) -> str:
    with open(path.expanduser(macaroon_path), "rb") as f:
        macaroon_bytes: bytes = f.read()

    return macaroon_bytes.hex().upper()


class LndRestWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""

    def __init__(self):
        endpoint = getenv("LND_REST_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Grpc-Metadata-macaroon": macaroon_to_hex(getenv("LND_ADMIN_MACAROON"))}
        self.auth_invoice = {"Grpc-Metadata-macaroon": macaroon_to_hex(getenv("LND_INVOICE_MACAROON"))}
        self.auth_read = {"Grpc-Metadata-macaroon": macaroon_to_hex(getenv("LND_READ_MACAROON"))}
        self.auth_cert = getenv("LND_CERT")

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        r = post(
            url=f"{self.endpoint}/v1/invoices",
            headers=self.auth_invoice,
            verify=self.auth_cert,
            json={"value": amount, "memo": memo, "private": True},
        )

        ok, checking_id, payment_request, error_message = r.ok, None, None, None

        if r.ok:
            data = r.json()
            payment_request = data["payment_request"]

        r = get(url=f"{self.endpoint}/v1/payreq/{payment_request}", headers=self.auth_read, verify=self.auth_cert,)

        if r.ok:
            checking_id = r.json()["payment_hash"].replace("/", "_")
            error_message = None
            ok = True

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(
            url=f"{self.endpoint}/v1/channels/transactions",
            headers=self.auth_admin,
            verify=self.auth_cert,
            json={"payment_request": bolt11},
        )
        ok, checking_id, fee_msat, error_message = r.ok, None, 0, None
        r = get(url=f"{self.endpoint}/v1/payreq/{bolt11}", headers=self.auth_admin, verify=self.auth_cert,)

        if r.ok:
            checking_id = r.json()["payment_hash"]
        else:
            error_message = r.json()["error"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        checking_id = checking_id.replace("_", "/")

        r = get(url=f"{self.endpoint}/v1/invoice/{checking_id}", headers=self.auth_invoice, verify=self.auth_cert,)

        if not r or not r.json()["settled"]:
            return PaymentStatus(None)

        return PaymentStatus(r.json()["settled"])

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = get(
            url=f"{self.endpoint}/v1/payments",
            headers=self.auth_admin,
            verify=self.auth_cert,
            params={"include_incomplete": "True", "max_payments": "20"},
        )

        if not r.ok:
            return PaymentStatus(None)

        payments = [p for p in r.json()["payments"] if p["payment_hash"] == checking_id]
        payment = payments[0] if payments else None

        # check payment.status: https://api.lightning.community/rest/index.html?python#peersynctype
        statuses = {"UNKNOWN": None, "IN_FLIGHT": None, "SUCCEEDED": True, "FAILED": False}

        return PaymentStatus(statuses[payment["status"]])
