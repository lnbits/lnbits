import asyncio
from collections.abc import AsyncGenerator

from bolt11.decode import decode
from grpc.aio import AioRpcError
from loguru import logger

from lnbits.helpers import normalize_endpoint, sha256s
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
    """
    Utilizing Boltz Client gRPC interface

    gRPC Bindings can be updated by running lnbits/wallets/boltz_grpc_files/update.sh
    """

    async def cleanup(self):
        logger.warning("Cleaning up BoltzWallet...")

    def __init__(self):
        if not settings.boltz_client_endpoint:
            raise ValueError(
                "cannot initialize BoltzWallet: missing boltz_client_endpoint"
            )

        self.endpoint = normalize_endpoint(
            settings.boltz_client_endpoint, add_proto=True
        )

        self.metadata = None
        if settings.boltz_client_macaroon:
            try:
                macaroon = load_macaroon(settings.boltz_client_macaroon)
                self.metadata = [("macaroon", macaroon)]
            except Exception as e:
                logger.error(f"BoltzWallet failed to load macaroon: {e}")

        if settings.boltz_client_cert:
            cert = open(settings.boltz_client_cert, "rb").read()
            creds = grpc.ssl_channel_credentials(cert)
            channel = grpc.aio.secure_channel(settings.boltz_client_endpoint, creds)
        else:
            channel = grpc.aio.insecure_channel(settings.boltz_client_endpoint)

        self.rpc = boltzrpc_pb2_grpc.BoltzStub(channel)
        self.wallet_id = 0
        self.wallet_name = "lnbits"
        self.wallet_ready = False

    async def status(self) -> StatusResponse:
        if self.wallet_ready is False:
            self.wallet_ready = True
            if settings.boltz_mnemonic:  # restore wallet from mnemonic
                await self._restore_boltz_wallet(
                    settings.boltz_mnemonic,
                    settings.boltz_client_password,
                )
            else:  # create new wallet
                await self._create_boltz_wallet()
        try:
            request = boltzrpc_pb2.GetWalletRequest(name=self.wallet_name)
            response: boltzrpc_pb2.Wallet = await self.rpc.GetWallet(
                request, metadata=self.metadata
            )
        except AioRpcError as exc:
            logger.warning(exc)
            return StatusResponse(
                "make sure you have macaroon and certificate configured,"
                "unless your client runs without",
                0,
            )

        self.wallet_id = response.id

        return StatusResponse(None, response.balance.total * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        pair = boltzrpc_pb2.Pair(to=boltzrpc_pb2.LBTC)
        request = boltzrpc_pb2.CreateReverseSwapRequest(
            amount=amount,
            pair=pair,
            wallet_id=self.wallet_id,
            accept_zero_conf=True,
            external_pay=True,
        )
        if memo is not None:
            # boltz rejects nbsp char (produced by JS Intl.NumberFormat api)
            request.description = memo.replace("\xa0", " ")
        response: boltzrpc_pb2.CreateReverseSwapResponse
        try:
            response = await self.rpc.CreateReverseSwap(request, metadata=self.metadata)
        except AioRpcError as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=exc.details())
        fee_msat = response.routing_fee_milli_sat
        return InvoiceResponse(
            ok=True,
            checking_id=response.id,
            payment_request=response.invoice,
            fee_msat=fee_msat,
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:

        pair = boltzrpc_pb2.Pair(**{"from": boltzrpc_pb2.LBTC})
        try:
            pair_info: boltzrpc_pb2.PairInfo
            pair_request = boltzrpc_pb2.GetPairInfoRequest(
                type=boltzrpc_pb2.SUBMARINE, pair=pair
            )
            pair_info = await self.rpc.GetPairInfo(pair_request, metadata=self.metadata)
            invoice = decode(bolt11)

            if not invoice.amount_msat:
                raise ValueError("amountless invoice")

            service_fee: float = invoice.amount_msat * pair_info.fees.percentage / 100
            estimate = int(service_fee + pair_info.fees.miner_fees * 1000)
            if estimate > fee_limit_msat:
                error = f"fee of {estimate} msat exceeds limit of {fee_limit_msat} msat"

                return PaymentResponse(ok=False, error_message=error)

            request = boltzrpc_pb2.CreateSwapRequest(
                invoice=bolt11,
                pair=pair,
                wallet_id=self.wallet_id,
                zero_conf=True,
                send_from_internal=True,
            )
            response: boltzrpc_pb2.CreateSwapResponse
            response = await self.rpc.CreateSwap(request, metadata=self.metadata)

            # empty swap id means that the invoice included a magic routing hint and was
            # paid on the liquid network directly
            # docs: https://docs.boltz.exchange/api/magic-routing-hints
            if response.id == "":
                # note that there is no way to provide a checking id here,
                # but there is no need since it immediately is considered as successfull
                logger.warning(
                    "Boltz invoice paid directly on liquid network using magic routing"
                )
                return PaymentResponse(ok=True, checking_id=invoice.payment_hash)
        except AioRpcError as exc:
            logger.warning(exc)
            return PaymentResponse(ok=False, error_message=exc.details())

        try:
            info_request = boltzrpc_pb2.GetSwapInfoRequest(id=response.id)
            info: boltzrpc_pb2.GetSwapInfoResponse
            async for info in self.rpc.GetSwapInfoStream(
                info_request, metadata=self.metadata
            ):
                if info.swap.state == boltzrpc_pb2.SUCCESSFUL:
                    fee_msat = (info.swap.onchain_fee + info.swap.service_fee) * 1000
                    logger.debug(
                        f"Boltz swap successful, status: {info.swap.status}"
                        f"fee_msat: {fee_msat}"
                    )
                    return PaymentResponse(
                        ok=True,
                        checking_id=invoice.payment_hash,
                        fee_msat=fee_msat,
                        preimage=info.swap.preimage,
                    )
                elif info.swap.error != "":
                    return PaymentResponse(ok=False, error_message=info.swap.error)
            return PaymentResponse(
                ok=False, error_message="stream stopped unexpectedly"
            )
        except AioRpcError as exc:
            logger.warning(exc)
            return PaymentResponse(ok=False, error_message=exc.details())

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            request = boltzrpc_pb2.GetSwapInfoRequest(id=checking_id)
            response: boltzrpc_pb2.GetSwapInfoResponse = await self.rpc.GetSwapInfo(
                request,
                metadata=self.metadata,
            )
            swap = response.reverse_swap
        except AioRpcError as exc:
            logger.warning(exc)
            return PaymentPendingStatus()
        if swap.state == boltzrpc_pb2.SwapState.SUCCESSFUL:
            fee_msat = (
                swap.service_fee + swap.onchain_fee
            ) * 1000 + swap.routing_fee_msat
            logger.debug(
                f"Boltz swap successful, status: {swap.status}, fee_msat: {fee_msat}"
            )
            return PaymentSuccessStatus(
                fee_msat=fee_msat,
                preimage=swap.preimage,
            )
        elif swap.state == boltzrpc_pb2.SwapState.PENDING:
            return PaymentPendingStatus()

        return PaymentFailedStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            checking_id_bytes = bytes.fromhex(checking_id)
            request = boltzrpc_pb2.GetSwapInfoRequest(payment_hash=checking_id_bytes)
            response: boltzrpc_pb2.GetSwapInfoResponse = await self.rpc.GetSwapInfo(
                request,
                metadata=self.metadata,
            )
            swap = response.swap
        except AioRpcError as exc:
            logger.warning(exc)
            return PaymentPendingStatus()
        if swap.state == boltzrpc_pb2.SwapState.SUCCESSFUL:
            fee_msat = (swap.service_fee + swap.onchain_fee) * 1000
            logger.debug(
                f"Boltz swap successful, status: {swap.status}, fee_msat: {fee_msat}"
            )
            return PaymentSuccessStatus(
                fee_msat=fee_msat,
                preimage=swap.preimage,
            )
        elif swap.state == boltzrpc_pb2.SwapState.PENDING:
            return PaymentPendingStatus()

        return PaymentFailedStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                request = boltzrpc_pb2.GetSwapInfoRequest()
                info: boltzrpc_pb2.GetSwapInfoResponse
                async for info in self.rpc.GetSwapInfoStream(
                    request, metadata=self.metadata
                ):
                    reverse = info.reverse_swap
                    if (
                        reverse
                        and reverse.state == boltzrpc_pb2.SUCCESSFUL
                        and reverse.status == "invoice.settled"
                    ):
                        fee_msat = ((reverse.service_fee + reverse.onchain_fee) * 1000,)
                        logger.debug(
                            f"Boltz reverse swap settled: {reverse.id}, "
                            f"fee_msat: {fee_msat}"
                        )
                        yield reverse.id
            except Exception as exc:
                logger.error(
                    f"lost connection to boltz client swap stream: '{exc}', retrying in"
                    " 5 seconds"
                )
                await asyncio.sleep(5)

    async def _check_wallet_exists(
        self, wallet_name: str
    ) -> boltzrpc_pb2.Wallet | None:
        try:
            request = boltzrpc_pb2.GetWalletRequest(name=wallet_name)
            response = await self.rpc.GetWallet(request, metadata=self.metadata)
            return response
        except AioRpcError:
            return None

    async def _delete_wallet(self, wallet_id: int) -> None:
        logger.info(f"Deleting wallet '{wallet_id}'")
        delete_request = boltzrpc_pb2.RemoveWalletRequest(id=wallet_id)
        await self.rpc.RemoveWallet(delete_request, metadata=self.metadata)

    async def _restore_wallet(self, wallet_name: str, mnemonic: str, password: str):
        logger.info(f"Restoring wallet '{wallet_name}' from mnemonic")
        credentials = boltzrpc_pb2.WalletCredentials(mnemonic=mnemonic)
        params = boltzrpc_pb2.WalletParams(
            name=wallet_name,
            currency=boltzrpc_pb2.LBTC,
            password=password,
        )
        restore_request = boltzrpc_pb2.ImportWalletRequest(
            credentials=credentials, params=params
        )
        response = await self.rpc.ImportWallet(restore_request, metadata=self.metadata)
        return response

    async def _create_wallet(self, wallet_name: str, password: str) -> str:
        logger.info(f"Creating new wallet '{wallet_name}'")
        params = boltzrpc_pb2.WalletParams(
            name=wallet_name,
            currency=boltzrpc_pb2.LBTC,
            password=password,
        )
        create_request = boltzrpc_pb2.CreateWalletRequest(params=params)
        response = await self.rpc.CreateWallet(create_request, metadata=self.metadata)
        return response.mnemonic

    async def _restore_boltz_wallet(self, mnemonic: str, password: str):
        try:
            # delete the wallet with to name without hashing first if it exists
            wallet = await self._check_wallet_exists(self.wallet_name)
            if wallet:
                await self._delete_wallet(wallet.id)

            # recreate the wallet with the hashed name
            self.wallet_name = sha256s(mnemonic + password)
            wallet = await self._check_wallet_exists(self.wallet_name)
            if wallet:
                logger.success("✅ Boltz wallet exists.")
                return
            await self._restore_wallet(self.wallet_name, mnemonic, password)
            logger.success("✅ Boltz wallet restored from existing mnemonic")
        except Exception as e:
            logger.error(f"❌ Failed to restore Boltz wallet: {e}")

    async def _create_boltz_wallet(self):
        try:
            # delete the wallet with to name without hashing first if it exists
            wallet = await self._check_wallet_exists(self.wallet_name)
            if wallet:
                await self._delete_wallet(wallet.id)

            logger.info("No Mnemonic found for Boltz wallet, creating wallet...")
            mnemonic = await self._create_wallet(
                self.wallet_name, settings.boltz_client_password
            )
            logger.success("✅ Boltz wallet created successfully")
            settings.boltz_mnemonic = mnemonic
            from lnbits.core.crud.settings import set_settings_field

            await set_settings_field("boltz_mnemonic", mnemonic)

        except Exception as e:
            logger.error(f"❌ Failed to create Boltz wallet: {e}")
