import trio  # type: ignore
import httpx
from os import getenv
from typing import Optional, Dict, AsyncGenerator

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LNbitsWallet(Wallet):
    """https://github.com/lnbits/lnbits"""

    def __init__(self):
        self.endpoint = getenv("LNBITS_ENDPOINT")

        key = getenv("LNBITS_KEY") or getenv("LNBITS_ADMIN_KEY") or getenv("LNBITS_INVOICE_KEY")
        self.key = {"X-Api-Key": key}

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        data: Dict = {"out": False, "amount": amount}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        else:
            data["memo"] = memo or ""

        r = httpx.post(
            url=f"{self.endpoint}/api/v1/payments",
            headers=self.key,
            json=data,
        )
        ok, checking_id, payment_request, error_message = not r.is_error, None, None, None

        if r.is_error:
            error_message = r.json()["message"]
        else:
            data = r.json()
            checking_id, payment_request = data["checking_id"], data["payment_request"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        r = httpx.post(url=f"{self.endpoint}/api/v1/payments", headers=self.key, json={"out": True, "bolt11": bolt11})
        ok, checking_id, fee_msat, error_message = not r.is_error, None, 0, None

        if r.is_error:
            error_message = r.json()["message"]
        else:
            data = r.json()
            checking_id = data["checking_id"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = httpx.get(url=f"{self.endpoint}/api/v1/payments/{checking_id}", headers=self.key)

        if r.is_error:
            return PaymentStatus(None)

        return PaymentStatus(r.json()["paid"])

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = httpx.get(url=f"{self.endpoint}/api/v1/payments/{checking_id}", headers=self.key)

        if r.is_error:
            return PaymentStatus(None)

        return PaymentStatus(r.json()["paid"])

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        print("lnbits does not support paid invoices stream yet")
        await trio.sleep(5)
        yield ""
