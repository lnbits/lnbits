from requests import Response, get, post

from .base import InvoiceResponse, TxStatus, Wallet


class OpennodeWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""

    def __init__(self, *, endpoint: str, admin_key: str, invoice_key: str):
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth_admin = {"Authorization": admin_key}
        self.auth_invoice = {"Authorization": invoice_key}



    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        payment_hash, payment_request = None, None
        r = post(
            url=f"{self.endpoint}/v1/charges",
            headers=self.auth_invoice,
            json={"amount": f"{amount}", "description": memo},  # , "private": True},
        )
        if r.ok:
            data = r.json()
            payment_hash, payment_request = data["data"]["id"], data["data"]["lightning_invoice"]["payreq"]

        return InvoiceResponse(r, payment_hash, payment_request)

    def get_invoice_status(self, payment_hash: str) -> TxStatus:
        print(f"{self.endpoint}/v1/charge/{payment_hash}")
        print(self.auth_invoice)
        r = get(url=f"{self.endpoint}/v1/charge/{payment_hash}", headers=self.auth_invoice)
        data = r.json()
        
        if r.ok:
            data = r.json()
            if data["data"]["status"] != "paid":
                return TxStatus(r, None)
            else:
                return TxStatus(r, True)

        else:
            return TxStatus(r, False)

        

    def pay_invoice(self, bolt11: str) -> Response:
        payment_hash = None
        r = post(
            url=f"{self.endpoint}/v2/withdrawals",
            headers=self.auth_admin,
            json={"type": "ln", "address": bolt11},
        )

        if r.ok:
            data = r.json()
            payment_hash = data["data"]["id"]

        return (r, payment_hash)

    def get_payment_status(self, payment_hash: str) -> TxStatus:
        r = get(url=f"{self.endpoint}/v1/withdrawal/{payment_hash}", headers=self.auth_admin)

        print(f"{self.endpoint}/v1/withdrawal/{payment_hash}")

        if r.ok:
            data = r.json()
            if ["data"]["status"] != "confirmed":
                return TxStatus(r, None)
            else:
                return TxStatus(r, True)
        else:
            return TxStatus(r, False)

        