import requests

from abc import ABC, abstractmethod
from requests import Response


class WalletResponse(Response):
    """TODO: normalize different wallet responses
    """


class Wallet(ABC):
    @abstractmethod
    def create_invoice(self, amount: int, memo: str = "") -> WalletResponse:
        pass

    @abstractmethod
    def pay_invoice(self, bolt11: str) -> WalletResponse:
        pass

    def get_invoice_status(self, payment_hash: str) -> WalletResponse:
        pass


class LndHubWallet(Wallet):
    def __init__(self, *, uri: str):
        raise NotImplementedError


class LntxbotWallet(Wallet):
    def __init__(self, *, endpoint: str, admin_key: str, invoice_key: str) -> WalletResponse:
        self.endpoint = endpoint
        self.auth_admin = {"Authorization": f"Basic {admin_key}"}
        self.auth_invoice = {"Authorization": f"Basic {invoice_key}"}

    def create_invoice(self, amount: int, memo: str = "") -> WalletResponse:
        return requests.post(
            url=f"{self.endpoint}/addinvoice", headers=self.auth_invoice, json={"amt": amount, "memo": memo}
        )

    def pay_invoice(self, bolt11: str) -> WalletResponse:
        return requests.post(url=f"{self.endpoint}/payinvoice", headers=self.auth_admin, json={"invoice": bolt11})

    def get_invoice_status(self, payment_hash: str) -> Response:
        return requests.post(url=f"{self.endpoint}/invoicestatus/{payment_hash}", headers=self.auth_invoice)
