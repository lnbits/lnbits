import asyncio
import hashlib
from collections.abc import AsyncGenerator

import httpx
from bolt11 import Bolt11Exception
from bolt11 import decode as bolt11_decode
from loguru import logger

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class LNPayWallet(Wallet):
    """https://docs.lnpay.co/"""

    def __init__(self):
        if not settings.lnpay_api_endpoint:
            raise ValueError(
                "cannot initialize LNPayWallet: missing lnpay_api_endpoint"
            )
        if not settings.lnpay_api_key:
            raise ValueError("cannot initialize LNPayWallet: missing lnpay_api_key")

        super().__init__()
        wallet_key = settings.lnpay_wallet_key or settings.lnpay_admin_key
        if not wallet_key:
            raise ValueError(
                "cannot initialize LNPayWallet: "
                "missing lnpay_wallet_key or lnpay_admin_key"
            )
        self.wallet_key = wallet_key
        self.endpoint = normalize_endpoint(settings.lnpay_api_endpoint)
        self.payment_ids: dict[str, str] = {}

        headers = {
            "X-Api-Key": settings.lnpay_api_key,
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=headers)

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

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
                f"Wallet {data['user_label']} (data['id']) not active, but"
                f" {data['statusType']['name']}",
                0,
            )

        return StatusResponse(None, data["balance"] * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        data: dict = {"num_satoshis": f"{amount}"}
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
        if r.status_code == 201:
            data = r.json()
            self.pending_invoices.append(data["id"])
            return InvoiceResponse(
                ok=True,
                payment_request=data["payment_request"],
            )
        return InvoiceResponse(
            ok=False,
            error_message=r.text,
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            checking_id = bolt11_decode(bolt11).payment_hash
        except Bolt11Exception as exc:
            return PaymentResponse(ok=False, error_message=str(exc))

        try:
            r = await self.client.post(
                f"/wallet/{self.wallet_key}/withdraw",
                json={"payment_request": bolt11},
                timeout=None,
            )
            data = r.json()
        except Exception as exc:
            logger.warning(exc)
            return PaymentResponse(
                checking_id=checking_id,
                error_message="Unable to determine payment status.",
            )

        if r.is_error:
            error_message = data.get("message", r.text)
            return PaymentResponse(
                ok=False if r.is_client_error else None,
                checking_id=checking_id,
                error_message=error_message,
            )

        try:
            payment_data = data["lnTx"]
            provider_id = payment_data["id"]
        except (KeyError, TypeError) as exc:
            logger.warning(exc)
            return PaymentResponse(
                checking_id=checking_id,
                error_message="Server error: 'missing required fields'",
            )

        self.payment_ids[checking_id] = provider_id
        preimage = payment_data.get("payment_preimage")
        if not preimage:
            return PaymentResponse(
                checking_id=checking_id,
                error_message="Payment status is pending.",
            )
        return PaymentResponse(
            ok=True, checking_id=checking_id, fee_msat=0, preimage=preimage
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return await self.get_payment_status(checking_id)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        provider_id = self.payment_ids.get(checking_id, checking_id)
        r = await self.client.get(
            url=f"/lntx/{provider_id}",
        )

        if r.is_error:
            return PaymentPendingStatus()

        data = r.json()
        preimage = data["payment_preimage"]
        fee_msat = data["fee_msat"]
        statuses = {0: None, 1: True, -1: False}
        status = PaymentStatus(statuses[data["settled"]], fee_msat, preimage)
        if status.success or status.failed:
            self.payment_ids.pop(checking_id, None)
        return status

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while settings.lnbits_running:
            value = await self.queue.get()
            yield value
