from os import getenv
import os
from requests import get, post
from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LndRestWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""


    def __init__(self):

        endpoint = getenv("LND_REST_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        print(self.endpoint)
        self.auth_admin = {"Grpc-Metadata-macaroon": getenv("LND_REST_ADMIN_MACAROON")}
        self.auth_invoice = {"Grpc-Metadata-macaroon": getenv("LND_REST_INVOICE_MACAROON")}
        self.auth_read = {"Grpc-Metadata-macaroon": getenv("LND_REST_READ_MACAROON")}
        self.auth_cert = getenv("LND_REST_CERT")


    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:

        r = post(
            url=f"{self.endpoint}/v1/invoices",
            headers=self.auth_invoice, verify=self.auth_cert,
            json={"value": amount, "memo": memo, "private": True},
        )
        print(self.auth_invoice)

        ok, checking_id, payment_request, error_message = r.ok, None, None, None

        if r.ok:
            data = r.json()
            payment_request = data["payment_request"]

        r = get(url=f"{self.endpoint}/v1/payreq/{payment_request}", headers=self.auth_read, verify=self.auth_cert,)
        print(r)
        if r.ok:
            dataa = r.json()
            checking_id = dataa["payment_hash"]
            error_message = None
            ok = True

        return InvoiceResponse(ok, checking_id, payment_request, error_message)


    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = post(url=f"{self.endpoint}/v2/withdrawals", headers=self.auth_admin, verify=self.auth_cert, json={"type": "ln", "address": bolt11})
        ok, checking_id, fee_msat, error_message = r.ok, None, 0, None

        if r.ok:
            data = r.json()["data"]
            checking_id, fee_msat = data["id"], data["fee"] * 1000
        else:
            error_message = r.json()["message"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)


    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/v1/charge/{checking_id}", headers=self.auth_invoice, verify=self.auth_cert)

        if not r.ok:
            return PaymentStatus(None)

        statuses = {0: None, 1: True, -1: False}
        return PaymentStatus(statuses[r.json()["data"]["status"]])

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = get(url=f"{self.endpoint}/v1/withdrawal/{checking_id}", headers=self.auth_admin, verify=self.auth_cert)

        if not r.ok:
            return PaymentStatus(None)

        statuses = {0: None, 1: True, -1: False}
        return PaymentStatus(statuses[r.json()["data"]["status"]])
