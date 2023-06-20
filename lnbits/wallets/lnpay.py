import asyncio
import hashlib
import json
from http import HTTPStatus
from typing import AsyncGenerator, Dict, Optional

import httpx
from fastapi import HTTPException
from loguru import logger

from lnbits.settings import settings

from ..core.models import Payment, PaymentStatus
from .base import InvoiceResponse, PaymentResponse, StatusResponse, Wallet


class LNPayWallet(Wallet):
    """https://docs.lnpay.co/"""

    def __init__(self):
        endpoint = settings.lnpay_api_endpoint
        wallet_key = settings.lnpay_wallet_key or settings.lnpay_admin_key

        if not endpoint or not wallet_key or not settings.lnpay_api_key:
            raise Exception("cannot initialize lnpay")

        self.wallet_key = wallet_key
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth = {"X-Api-Key": settings.lnpay_api_key}
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.auth)

    async def cleanup(self):
        await self.client.aclose()

    async def status(self) -> StatusResponse:
        url = f"/wallet/{self.wallet_key}"
        try:
            r = await self.client.get(url, timeout=60)
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
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        data: Dict = {"num_satoshis": f"{amount}"}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        elif unhashed_description:
            data["description_hash"] = hashlib.sha256(unhashed_description).hexdigest()
        else:
            data["memo"] = memo or ""

        r = await self.client.post(
            f"/wallet/{self.wallet_key}/invoice",
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

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        r = await self.client.post(
            f"/wallet/{self.wallet_key}/withdraw",
            json={"payment_request": bolt11},
            timeout=None,
        )

        try:
            data = r.json()
        except:
            return PaymentResponse(
                False, None, 0, None, f"Got invalid JSON: {r.text[:200]}"
            )

        if r.is_error:
            return PaymentResponse(False, None, None, None, data["message"])

        checking_id = data["lnTx"]["id"]
        fee_msat = 0
        preimage = data["lnTx"]["payment_preimage"]
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, payment: Payment) -> PaymentStatus:
        return await self.get_payment_status(payment)

    async def get_payment_status(self, payment: Payment) -> PaymentStatus:
        r = await self.client.get(
            url=f"/lntx/{payment.checking_id}",
        )

        if r.is_error:
            return PaymentStatus(None)

        data = r.json()
        preimage = data["payment_preimage"]
        fee_msat = data["fee_msat"]
        statuses = {0: None, 1: True, -1: False}
        return PaymentStatus(statuses[data["settled"]], fee_msat, preimage)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value

    async def webhook_listener(self):
        # TODO: request.get_data is undefined, was it something with Flask or quart?
        # probably issue introduced when refactoring?
        text: str = await request.get_data()  # type: ignore
        try:
            data = json.loads(text)
        except json.decoder.JSONDecodeError:
            logger.error(f"got something wrong on lnpay webhook endpoint: {text[:200]}")
            data = None
        if (
            type(data) is not dict
            or "event" not in data
            or data["event"].get("name") != "wallet_receive"
        ):
            raise HTTPException(status_code=HTTPStatus.NO_CONTENT)

        lntx_id = data["data"]["wtx"]["lnTx"]["id"]
        r = await self.client.get(f"/lntx/{lntx_id}?fields=settled")
        data = r.json()
        if data["settled"]:
            await self.queue.put(lntx_id)

        raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
