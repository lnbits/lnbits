import json
import trio
import httpx
from os import getenv
from http import HTTPStatus
from typing import Optional, Dict, AsyncGenerator
from quart import request

from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
)


class LNPayWallet(Wallet):
    """https://docs.lnpay.co/"""

    def __init__(self):
        endpoint = getenv("LNPAY_API_ENDPOINT", "https://lnpay.co/v1")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.wallet_key = getenv("LNPAY_WALLET_KEY") or getenv("LNPAY_ADMIN_KEY")
        self.auth = {"X-Api-Key": getenv("LNPAY_API_KEY")}

    async def status(self) -> StatusResponse:
        url = f"{self.endpoint}/wallet/{self.wallet_key}"
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=self.auth, timeout=60)
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse(f"Unable to connect to '{url}'", 0)

        if r.is_error:
            return StatusResponse(r.text[:250], 0)

        data = r.json()
        if data["statusType"]["name"] != "active":
            return StatusResponse(
                f"Wallet {data['user_label']} (data['id']) not active, but {data['statusType']['name']}",
                0,
            )

        return StatusResponse(None, data["balance"] * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        data: Dict = {"num_satoshis": f"{amount}"}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        else:
            data["memo"] = memo or ""

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.endpoint}/wallet/{self.wallet_key}/invoice",
                headers=self.auth,
                json=data,
                timeout=60,
            )
        ok, checking_id, payment_request, error_message = (
            r.status_code == 201,
            None,
            None,
            r.text,
        )

        if ok:
            data = r.json()
            checking_id, payment_request = data["id"], data["payment_request"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    # WARNING: correct handling of fee_limit_msat is required to avoid security vulnerabilities!
    # The backend MUST NOT spend satoshis above invoice amount + fee_limit_msat.
    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.endpoint}/wallet/{self.wallet_key}/withdraw",
                headers=self.auth,
                json={"payment_request": bolt11},
                timeout=180,
            )

        try:
            data = r.json()
        except:
            return PaymentResponse(
                False, None, 0, None, f"Got invalid JSON: {r.text[:200]}"
            )

        if r.is_error:
            return PaymentResponse(False, None, 0, None, data["message"])

        checking_id = data["lnTx"]["id"]
        fee_msat = 0
        preimage = data["lnTx"]["payment_preimage"]
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return await self.get_payment_status(checking_id)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                url=f"{self.endpoint}/lntx/{checking_id}?fields=settled",
                headers=self.auth,
            )

        if r.is_error:
            return PaymentStatus(None)

        statuses = {0: None, 1: True, -1: False}
        return PaymentStatus(statuses[r.json()["settled"]])

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.send, receive = trio.open_memory_channel(0)
        async for value in receive:
            yield value

    async def webhook_listener(self):
        text: str = await request.get_data()
        try:
            data = json.loads(text)
        except json.decoder.JSONDecodeError:
            print(f"got something wrong on lnpay webhook endpoint: {text[:200]}")
            data = None
        if (
            type(data) is not dict
            or "event" not in data
            or data["event"].get("name") != "wallet_receive"
        ):
            return "", HTTPStatus.NO_CONTENT

        lntx_id = data["data"]["wtx"]["lnTx"]["id"]
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.endpoint}/lntx/{lntx_id}?fields=settled",
                headers=self.auth,
            )
            data = r.json()
            if data["settled"]:
                await self.send.send(lntx_id)

        return "", HTTPStatus.NO_CONTENT
