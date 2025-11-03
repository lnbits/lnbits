import asyncio
import base64
from collections.abc import AsyncGenerator
from hashlib import sha256
from os import environ

import grpc
from loguru import logger

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.lnd_grpc_files.invoices_pb2 import (
    AddHoldInvoiceRequest,
    AddHoldInvoiceResp,
    CancelInvoiceMsg,
    CancelInvoiceResp,
    LookupInvoiceMsg,
    SettleInvoiceMsg,
    SettleInvoiceResp,
)
from lnbits.wallets.lnd_grpc_files.invoices_pb2_grpc import InvoicesStub
from lnbits.wallets.lnd_grpc_files.lightning_pb2 import (
    AddInvoiceResponse,
    ChannelBalanceRequest,
    ChannelBalanceResponse,
    Invoice,
    InvoiceSubscription,
    Payment,
    PaymentFailureReason,
)
from lnbits.wallets.lnd_grpc_files.lightning_pb2_grpc import LightningStub
from lnbits.wallets.lnd_grpc_files.router_pb2 import (
    SendPaymentRequest,
    TrackPaymentRequest,
)
from lnbits.wallets.lnd_grpc_files.router_pb2_grpc import RouterStub

from .base import (
    Feature,
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)
from .macaroon import load_macaroon


def b64_to_bytes(checking_id: str) -> bytes:

    return base64.b64decode(checking_id.replace("_", "/"))


def bytes_to_b64(r_hash: bytes) -> str:
    return base64.b64encode(r_hash).decode().replace("/", "_")


def hex_to_b64(hex_str: str) -> str:
    try:
        return base64.b64encode(bytes.fromhex(hex_str)).decode()
    except ValueError:
        return ""


def hex_to_bytes(hex_str: str) -> bytes:
    try:
        return bytes.fromhex(hex_str)
    except Exception:
        return b""


def bytes_to_hex(b: bytes) -> str:
    return b.hex()


# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handhsake
# error when we communicate with the lnd rpc server.
environ["GRPC_SSL_CIPHER_SUITES"] = "HIGH+ECDSA"


class LndWallet(Wallet):
    rpc: LightningStub
    router_rpc: RouterStub
    invoices_rpc: InvoicesStub

    features = [Feature.holdinvoice]

    def __init__(self):
        if not settings.lnd_grpc_endpoint:
            raise ValueError("cannot initialize LndWallet: missing lnd_grpc_endpoint")
        if not settings.lnd_grpc_port:
            raise ValueError("cannot initialize LndWallet: missing lnd_grpc_port")

        cert_path = settings.lnd_grpc_cert or settings.lnd_cert
        if not cert_path:
            raise ValueError(
                "cannot initialize LndWallet: missing lnd_grpc_cert or lnd_cert"
            )

        self.endpoint = normalize_endpoint(settings.lnd_grpc_endpoint, add_proto=False)
        self.port = int(settings.lnd_grpc_port)

        macaroon = (
            settings.lnd_grpc_macaroon
            or settings.lnd_grpc_admin_macaroon
            or settings.lnd_grpc_invoice_macaroon
        )
        encrypted_macaroon = settings.lnd_grpc_macaroon_encrypted
        try:
            self.macaroon = load_macaroon(macaroon, encrypted_macaroon)
        except ValueError as exc:
            raise ValueError(f"cannot load macaroon for LndWallet: {exc!s}") from exc

        cert = open(cert_path, "rb").read()
        creds = grpc.ssl_channel_credentials(cert)
        auth_creds = grpc.metadata_call_credentials(self.metadata_callback)
        composite_creds = grpc.composite_channel_credentials(creds, auth_creds)
        channel = grpc.aio.secure_channel(
            f"{self.endpoint}:{self.port}", composite_creds
        )
        self.rpc = LightningStub(channel)
        self.router_rpc = RouterStub(channel)
        self.invoices_rpc = InvoicesStub(channel)

    def metadata_callback(self, _, callback):
        callback([("macaroon", self.macaroon)], None)

    async def cleanup(self):
        pass

    async def status(self) -> StatusResponse:
        try:
            req = ChannelBalanceRequest()
            res: ChannelBalanceResponse = await self.rpc.ChannelBalance(req)
        except Exception as exc:
            return StatusResponse(f"Unable to connect, got: '{exc}'", 0)

        return StatusResponse(None, res.balance * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:

        preimage = kwargs.get("preimage")
        if preimage:
            payment_hash = sha256(preimage.encode()).hexdigest()
        else:
            preimage, payment_hash = random_secret_and_hash()

        invoice = Invoice(
            value=amount,
            private=True,
            memo=memo or "",
            r_hash=bytes.fromhex(payment_hash),
            r_preimage=bytes.fromhex(preimage),
        )

        if kwargs.get("expiry"):
            invoice.expiry = kwargs.get("expiry", 3600)
        if description_hash:
            invoice.description_hash = description_hash
        elif unhashed_description:
            invoice.description_hash = sha256(unhashed_description).digest()

        try:
            res: AddInvoiceResponse = await self.rpc.AddInvoice(invoice)
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=str(exc))

        return InvoiceResponse(
            ok=True,
            checking_id=bytes_to_hex(res.r_hash),
            payment_request=res.payment_request,
            preimage=preimage,
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        # fee_limit_fixed = ln.FeeLimit(fixed=fee_limit_msat // 1000)
        req = SendPaymentRequest(
            payment_request=bolt11,
            fee_limit_msat=fee_limit_msat,
            timeout_seconds=30,
            no_inflight_updates=True,
        )
        try:
            res: Payment = await self.router_rpc.SendPaymentV2(req).read()
        except Exception as exc:
            logger.warning(exc)
            return PaymentResponse(error_message=str(exc))

        if res.status == Payment.PaymentStatus.SUCCEEDED:
            return PaymentResponse(
                ok=True,
                checking_id=res.payment_hash,
                fee_msat=abs(res.fee_msat),
                preimage=res.payment_preimage,
            )
        elif res.status == Payment.PaymentStatus.FAILED:
            error_message = PaymentFailureReason.Name(res.failure_reason)
            return PaymentResponse(
                ok=False, error_message=f"Payment failed: {error_message}"
            )
        elif res.status == Payment.PaymentStatus.IN_FLIGHT:
            return PaymentResponse(
                ok=None,
                checking_id=res.payment_hash,
                error_message="Payment is IN_FLIGHT.",
            )
        else:
            return PaymentResponse(
                ok=None,
                checking_id=res.payment_hash,
                error_message="Payment is non-existant.",
            )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r_hash = hex_to_bytes(checking_id)
            if len(r_hash) != 32:
                # this may happen if we switch between backend wallets
                # that use different checking_id formats
                raise ValueError
            req = LookupInvoiceMsg(payment_hash=r_hash)
            res: Invoice = await self.invoices_rpc.LookupInvoiceV2(req)
        except grpc.aio.AioRpcError as exc:
            logger.warning(
                f"LndWallet.get_invoice_status grpc exception: {exc.details()}"
            )
            return PaymentPendingStatus()
        except Exception as exc:
            logger.warning(f"LndWallet.get_invoice_status exception: {exc}")
            return PaymentPendingStatus()

        if res.settled:
            return PaymentSuccessStatus(preimage=res.r_preimage.hex())

        if res.state == Invoice.InvoiceState.CANCELED:
            return PaymentFailedStatus()

        return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        """
        This routine checks the payment status using router_rpc.TrackPaymentV2.
        https://lightning.engineering/api-docs/api/lnd/router/track-payment-v2/#lnrpcpayment
        """
        try:
            r_hash = hex_to_bytes(checking_id)
        except ValueError:
            logger.error(
                f"LndWallet: Invalid checking_id ({checking_id}),"
                " was the fundingsource changed? Returning pending status."
            )
            return PaymentPendingStatus()

        try:
            req = TrackPaymentRequest(payment_hash=r_hash)
            res = self.router_rpc.TrackPaymentV2(req)
        except grpc.aio.AioRpcError as exc:
            logger.error(
                f"Payment Status grpc exception: {exc.details() or exc.code()}"
            )
            return PaymentPendingStatus()
        except Exception as exc:  # most likely the payment wasn't found
            logger.error(f"Payment Status exception: {exc}")
            return PaymentPendingStatus()

        try:
            async for payment in res:
                if payment.status == Payment.PaymentStatus.SUCCEEDED:
                    return PaymentSuccessStatus(
                        fee_msat=abs(payment.fee_msat),
                        preimage=payment.payment_preimage,
                    )
                elif payment.status == Payment.PaymentStatus.FAILED:
                    logger.info(f"LND Payment failed: {payment.failure_reason}")
                    return PaymentFailedStatus()
                elif payment.status == Payment.PaymentStatus.IN_FLIGHT:
                    logger.info(f"LND Payment in flight: {checking_id}")
                    return PaymentPendingStatus()
        except grpc.aio.AioRpcError as exc:
            logger.error(
                f"Payment Status grpc exception: {exc.details() or exc.code()}"
            )
            return PaymentPendingStatus()

        logger.info(f"LND Payment non-existent: {checking_id}")
        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                req = InvoiceSubscription()
                async for i in self.rpc.SubscribeInvoices(req):
                    if not i.settled:
                        continue
                    checking_id = bytes_to_hex(i.r_hash)
                    yield checking_id
            except Exception as exc:
                logger.error(
                    f"lost connection to lnd invoices stream: '{exc}', "
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)

    async def create_hold_invoice(
        self,
        amount: int,
        payment_hash: str,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        hold_invoice = AddHoldInvoiceRequest(
            value=amount,
            hash=hex_to_bytes(payment_hash),
            private=True,
            memo=memo or "",
        )
        if kwargs.get("expiry"):
            hold_invoice.expiry = kwargs.get("expiry", 3600)
        if description_hash:
            hold_invoice.description_hash = description_hash
        elif unhashed_description:
            hold_invoice.description_hash = sha256(unhashed_description).digest()
        try:
            res: AddHoldInvoiceResp = await self.invoices_rpc.AddHoldInvoice(
                hold_invoice
            )
            logger.debug(f"AddHoldInvoice response: {res}")
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=str(exc))
        return InvoiceResponse(
            ok=True, checking_id=payment_hash, payment_request=res.payment_request
        )

    async def settle_hold_invoice(self, preimage: str) -> InvoiceResponse:
        try:
            req = SettleInvoiceMsg(preimage=hex_to_bytes(preimage))
            res: SettleInvoiceResp = await self.invoices_rpc.SettleInvoice(req)
            logger.debug(f"SettleInvoice response: {res}")
        except grpc.aio.AioRpcError as exc:
            return InvoiceResponse(
                ok=False, error_message=exc.details() or "unknown grpc exception"
            )
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=str(exc))
        return InvoiceResponse(ok=True, preimage=preimage)

    async def cancel_hold_invoice(self, payment_hash: str) -> InvoiceResponse:
        try:
            req = CancelInvoiceMsg(payment_hash=hex_to_bytes(payment_hash))
            res: CancelInvoiceResp = await self.invoices_rpc.CancelInvoice(req)
            logger.debug(f"CancelInvoice response: {res}")
        except Exception as exc:
            logger.warning(exc)
            # If we cannot cancel the invoice, we return an error message
            # and True for ok that should be ignored by the service
            return InvoiceResponse(
                ok=False, checking_id=payment_hash, error_message=str(exc)
            )
        # If we reach here, the invoice was successfully canceled and payment failed
        return InvoiceResponse(True, checking_id=payment_hash)
