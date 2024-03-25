import asyncio
from typing import AsyncGenerator, Optional

from grpc.aio import AioRpcError
from loguru import logger

from lnbits.settings import settings
from lnbits.wallets.boltz_grpc_files import boltzrpc_pb2, boltzrpc_pb2_grpc
from lnbits.wallets.lnd_grpc_files.lightning_pb2_grpc import grpc
from lnbits.wallets.macaroon.macaroon import load_macaroon

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)


class BoltzWallet(Wallet):
    """Utilizing Boltz Client Standalone API"""

    async def cleanup(self):
        logger.warning("Cleaning up BoltzWallet...")

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
        **_,
    ) -> InvoiceResponse:
        pair = boltzrpc_pb2.Pair(to=boltzrpc_pb2.LBTC)
        request = boltzrpc_pb2.CreateReverseSwapRequest(
            amount=amount,
            pair=pair,
            wallet=settings.boltz_client_wallet,
            accept_zero_conf=True,
            external_pay=True,
        )
        response: boltzrpc_pb2.CreateReverseSwapResponse
        try:
            response = await self.rpc.CreateReverseSwap(request)
        except AioRpcError as exc:
            return InvoiceResponse(ok=False, error_message=exc.details())
        return InvoiceResponse(
            ok=True, checking_id=response.id, payment_request=response.invoice
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        pair = boltzrpc_pb2.Pair(**{"from": boltzrpc_pb2.LBTC})
        request = boltzrpc_pb2.CreateSwapRequest(
            invoice=bolt11,
            pair=pair,
            wallet=settings.boltz_client_wallet,
            send_from_internal=True,
        )
        try:
            response: boltzrpc_pb2.CreateSwapResponse
            response = await self.rpc.CreateSwap(request)
        except AioRpcError as exc:
            return PaymentResponse(ok=False, error_message=exc.details())

        try:
            info_request = boltzrpc_pb2.GetSwapInfoRequest(id=response.id)
            info: boltzrpc_pb2.GetSwapInfoResponse
            async for info in self.rpc.GetSwapInfoStream(info_request):
                if info.swap.state == boltzrpc_pb2.SUCCESSFUL:
                    return PaymentResponse(
                        ok=True,
                        checking_id=response.id,
                        fee_msat=(info.swap.onchain_fee + info.swap.service_fee) * 1000,
                        preimage=info.swap.preimage,
                    )
                elif info.swap.error != "":
                    return PaymentResponse(ok=False, error_message=info.swap.error)
            return PaymentResponse(
                ok=False, error_message="stream stopped unexpectedly"
            )
        except AioRpcError as exc:
            return PaymentResponse(ok=False, error_message=exc.details())

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            response: boltzrpc_pb2.GetSwapInfoResponse = await self.rpc.GetSwapInfo(
                boltzrpc_pb2.GetSwapInfoRequest(id=checking_id)
            )
        except AioRpcError:
            return PaymentPendingStatus()
        if response.reverse_swap.state == boltzrpc_pb2.SwapState.SUCCESSFUL:
            return PaymentSuccessStatus()
        elif response.reverse_swap.state == boltzrpc_pb2.SwapState.PENDING:
            return PaymentPendingStatus()

        return PaymentFailedStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            response: boltzrpc_pb2.GetSwapInfoResponse = await self.rpc.GetSwapInfo(
                boltzrpc_pb2.GetSwapInfoRequest(id=checking_id)
            )
        except AioRpcError:
            return PaymentPendingStatus()

        if response.swap.state == boltzrpc_pb2.SwapState.SUCCESSFUL:
            return PaymentSuccessStatus()
        elif response.swap.state == boltzrpc_pb2.SwapState.PENDING:
            return PaymentPendingStatus()

        return PaymentFailedStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                request = boltzrpc_pb2.GetSwapInfoRequest()
                info: boltzrpc_pb2.GetSwapInfoResponse
                async for info in self.rpc.GetSwapInfoStream(request):
                    reverse = info.reverse_swap
                    if reverse and reverse.state == boltzrpc_pb2.SUCCESSFUL:
                        yield reverse.id
            except Exception as exc:
                logger.error(
                    f"lost connection to boltz client swap stream: '{exc}', retrying in"
                    " 5 seconds"
                )
                await asyncio.sleep(5)
