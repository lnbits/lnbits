try:
    import lndgrpc  # type: ignore
    from lndgrpc.common import ln  # type: ignore
except ImportError:  # pragma: nocover
    lndgrpc = None

import binascii
import base64
import hashlib
from os import getenv
from typing import Optional, Dict, AsyncGenerator

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


def parse_checking_id(checking_id: str) -> bytes:
    return base64.b64decode(
        checking_id.replace("_", "/"),
    )


def stringify_checking_id(r_hash: bytes) -> str:
    return (
        base64.b64encode(
            r_hash,
        )
        .decode("utf-8")
        .replace("/", "_")
    )


class LndWallet(Wallet):
    def __init__(self):
        if lndgrpc is None:  # pragma: nocover
            raise ImportError("The `lndgrpc` library must be installed to use `LndWallet`.")

        endpoint = getenv("LND_GRPC_ENDPOINT")
        endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        port = getenv("LND_GRPC_PORT")
        cert = getenv("LND_GRPC_CERT") or getenv("LND_CERT")
        auth_admin = getenv("LND_GRPC_ADMIN_MACAROON") or getenv("LND_ADMIN_MACAROON")
        auth_invoices = getenv("LND_GRPC_INVOICE_MACAROON") or getenv("LND_INVOICE_MACAROON")
        network = getenv("LND_GRPC_NETWORK", "mainnet")

        self.admin_rpc = lndgrpc.LNDClient(
            endpoint + ":" + port,
            cert_filepath=cert,
            network=network,
            macaroon_filepath=auth_admin,
        )

        self.invoices_rpc = lndgrpc.LNDClient(
            endpoint + ":" + port,
            cert_filepath=cert,
            network=network,
            macaroon_filepath=auth_invoices,
        )

        self.async_rpc = lndgrpc.AsyncLNDClient(
            endpoint + ":" + port,
            cert_filepath=cert,
            network=network,
            macaroon_filepath=auth_invoices,
        )

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        params: Dict = {"value": amount, "expiry": 600, "private": True}

        if description_hash:
            params["description_hash"] = description_hash  # as bytes directly
        else:
            params["memo"] = memo or ""

        try:
            req = ln.Invoice(**params)
            resp = self.invoices_rpc._ln_stub.AddInvoice(req)
        except Exception as exc:
            error_message = str(exc)
            return InvoiceResponse(False, None, None, error_message)

        checking_id = stringify_checking_id(resp.r_hash)
        payment_request = str(resp.payment_request)
        return InvoiceResponse(True, checking_id, payment_request, None)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        resp = self.admin_rpc.send_payment(payment_request=bolt11)

        if resp.payment_error:
            return PaymentResponse(False, "", 0, resp.payment_error)

        r_hash = hashlib.sha256(resp.payment_preimage).digest()
        checking_id = stringify_checking_id(r_hash)
        return PaymentResponse(True, checking_id, 0, None)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r_hash = parse_checking_id(checking_id)
            if len(r_hash) != 32:
                raise binascii.Error
        except binascii.Error:
            # this may happen if we switch between backend wallets
            # that use different checking_id formats
            return PaymentStatus(None)

        resp = self.invoices_rpc.lookup_invoice(r_hash.hex())
        if resp.settled:
            return PaymentStatus(True)

        return PaymentStatus(None)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(True)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        async for inv in self.async_rpc._ln_stub.SubscribeInvoices(ln.InvoiceSubscription()):
            if not inv.settled:
                continue

            checking_id = stringify_checking_id(inv.r_hash)
            yield checking_id
