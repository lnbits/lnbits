import asyncio
import hashlib
from typing import AsyncGenerator, Dict, Optional

from grpc.aio import AioRpcError

from lnbits.settings import settings
from lnbits.wallets.boltz_grpc_files import boltzrpc_pb2
from lnbits.wallets.boltz_grpc_files import boltzrpc_pb2_grpc
from lnbits.wallets.lnd_grpc_files.lightning_pb2_grpc import grpc
from lnbits.wallets.macaroon.macaroon import load_macaroon

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class BoltzWallet(Wallet):
    """Utilizing Boltz Client Standalone API"""

    def __init__(self):
        if not settings.boltz_client_endpoint:
            raise ValueError(
                "cannot initialize BoltzWallet: missing boltz_client_endpoint"
            )
        if not settings.boltz_client_macaroon:
            raise ValueError(
                "cannot initialize BoltzWallet: missing boltz_client_macaroon"
            )
        if not settings.boltz_client_wallet:
            raise ValueError(
                "cannot initialize BoltzWallet: missing boltz_client_wallet"
            )

        self.endpoint = self.normalize_endpoint(
            settings.boltz_client_endpoint, add_proto=True
        )

        self.macaroon = load_macaroon(settings.boltz_client_macaroon)
        if settings.boltz_client_cert:
            cert = open(settings.boltz_client_cert, "rb").read()
            grpc.aio.insecure_channel(settings.boltz_client_endpoint)
            creds = grpc.ssl_channel_credentials(cert)
            auth_creds = grpc.metadata_call_credentials(self.metadata_callback)
            composite_creds = grpc.composite_channel_credentials(creds, auth_creds)
            channel = grpc.aio.secure_channel(
                settings.boltz_client_endpoint, composite_creds
            )
        else:
            channel = grpc.aio.insecure_channel(settings.boltz_client_endpoint)
        self.rpc = boltzrpc_pb2_grpc.BoltzStub(channel)

    def metadata_callback(self, _, callback):
        callback([("macaroon", self.macaroon)], None)

    async def status(self) -> StatusResponse:
        try:
            request = boltzrpc_pb2.GetWalletRequest(name=settings.boltz_client_wallet)
            response: boltzrpc_pb2.Wallet = await self.rpc.GetWallet(request)
        except AioRpcError as exc:
            return StatusResponse(exc.details(), 0)

        return StatusResponse(None, response.balance.total * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        # https://api.getalby.com/invoices
        data: Dict = {"amount": f"{amount}"}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        elif unhashed_description:
            data["description_hash"] = hashlib.sha256(unhashed_description).hexdigest()
        else:
            data["memo"] = memo or ""

        r = await self.client.post(
            "/invoices",
            json=data,
            timeout=40,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        checking_id = data["payment_hash"]
        payment_request = data["payment_request"]
        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        r = await self.client.post(
            "/payments/bolt11",
            json={"invoice": bolt11},  # assume never need amount in body
            timeout=None,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()
        checking_id = data["payment_hash"]
        fee_msat = -data["fee"]
        preimage = data["payment_preimage"]

        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return await self.get_payment_status(checking_id)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(f"/invoices/{checking_id}")

        if r.is_error:
            return PaymentPendingStatus()

        data = r.json()

        statuses = {
            "CREATED": None,
            "SETTLED": True,
        }
        return PaymentStatus(statuses[data.get("state")], fee_msat=None, preimage=None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
