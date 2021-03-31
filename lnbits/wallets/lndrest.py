import trio  # type: ignore
import httpx
import json
import base64
from os import getenv
from typing import Optional, Dict, AsyncGenerator

from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
)


class LndRestWallet(Wallet):
    """https://api.lightning.community/rest/index.html#lnd-rest-api-reference"""

    def __init__(self):
        endpoint = getenv("LND_REST_ENDPOINT")
        endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        endpoint = (
            "https://" + endpoint if not endpoint.startswith("http") else endpoint
        )
        self.endpoint = endpoint

        macaroon = (
            getenv("LND_REST_MACAROON")
            or getenv("LND_ADMIN_MACAROON")
            or getenv("LND_REST_ADMIN_MACAROON")
            or getenv("LND_INVOICE_MACAROON")
            or getenv("LND_REST_INVOICE_MACAROON")
        )
        self.auth = {"Grpc-Metadata-macaroon": macaroon}
        self.cert = getenv("LND_REST_CERT")

    async def status(self) -> StatusResponse:
        try:
            async with httpx.AsyncClient(verify=self.cert) as client:
                r = await client.get(
                    f"{self.endpoint}/v1/balance/channels",
                    headers=self.auth,
                )
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse(f"Unable to connect to {self.endpoint}.", 0)

        try:
            data = r.json()
            if r.is_error:
                raise Exception
        except Exception:
            return StatusResponse(r.text[:200], 0)

        return StatusResponse(None, int(data["balance"]) * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        data: Dict = {
            "value": amount,
            "private": True,
        }
        if description_hash:
            data["description_hash"] = base64.b64encode(description_hash).decode(
                "ascii"
            )
        else:
            data["memo"] = memo or ""

        async with httpx.AsyncClient(verify=self.cert) as client:
            r = await client.post(
                url=f"{self.endpoint}/v1/invoices",
                headers=self.auth,
                json=data,
            )

        if r.is_error:
            error_message = r.text
            try:
                error_message = r.json()["error"]
            except Exception:
                pass
            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        payment_request = data["payment_request"]
        payment_hash = base64.b64decode(data["r_hash"]).hex()
        checking_id = payment_hash

        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:
        async with httpx.AsyncClient(verify=self.cert) as client:
            r = await client.post(
                url=f"{self.endpoint}/v1/channels/transactions",
                headers=self.auth,
                json={"payment_request": bolt11},
                timeout=180,
            )

        if r.is_error:
            error_message = r.text
            try:
                error_message = r.json()["error"]
            except:
                pass
            return PaymentResponse(False, None, 0, None, error_message)

        data = r.json()
        payment_hash = data["payment_hash"]
        checking_id = payment_hash
        preimage = base64.b64decode(data["payment_preimage"]).hex()
        return PaymentResponse(True, checking_id, 0, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        checking_id = checking_id.replace("_", "/")

        async with httpx.AsyncClient(verify=self.cert) as client:
            r = await client.get(
                url=f"{self.endpoint}/v1/invoice/{checking_id}",
                headers=self.auth,
            )

        if r.is_error or not r.json().get("settled"):
            # this must also work when checking_id is not a hex recognizable by lnd
            # it will return an error and no "settled" attribute on the object
            return PaymentStatus(None)

        return PaymentStatus(True)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        async with httpx.AsyncClient(verify=self.cert) as client:
            r = await client.get(
                url=f"{self.endpoint}/v1/payments",
                headers=self.auth,
                params={"max_payments": "20", "reversed": True},
            )

        if r.is_error:
            return PaymentStatus(None)

        # check payment.status:
        # https://api.lightning.community/rest/index.html?python#peersynctype
        statuses = {
            "UNKNOWN": None,
            "IN_FLIGHT": None,
            "SUCCEEDED": True,
            "FAILED": False,
        }

        # for some reason our checking_ids are in base64 but the payment hashes
        # returned here are in hex, lnd is weird
        checking_id = base64.b64decode(checking_id).hex()

        for p in r.json()["payments"]:
            if p["payment_hash"] == checking_id:
                return PaymentStatus(statuses[p["status"]])

        return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        url = self.endpoint + "/v1/invoices/subscribe"

        while True:
            try:
                async with httpx.AsyncClient(
                    timeout=None,
                    headers=self.auth,
                    verify=self.cert,
                ) as client:
                    async with client.stream("GET", url) as r:
                        async for line in r.aiter_lines():
                            try:
                                inv = json.loads(line)["result"]
                                if not inv["settled"]:
                                    continue
                            except:
                                continue

                            payment_hash = base64.b64decode(inv["r_hash"]).hex()
                            yield payment_hash
            except (OSError, httpx.ConnectError, httpx.ReadError):
                pass

            print("lost connection to lnd invoices stream, retrying in 5 seconds")
            await trio.sleep(5)
