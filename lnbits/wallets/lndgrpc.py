try:
    import lndgrpc  # type: ignore
    from lndgrpc.common import ln  # type: ignore
except ImportError:  # pragma: nocover
    lndgrpc = None

try:
    import purerpc  # type: ignore
except ImportError:  # pragma: nocover
    purerpc = None

import binascii
import base64
import hashlib
from os import getenv
from typing import Optional, Dict, AsyncGenerator

from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
)


def get_ssl_context(cert_path: str):
    import ssl

    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_TLSv1
    context.options |= ssl.OP_NO_TLSv1_1
    context.options |= ssl.OP_NO_COMPRESSION
    context.set_ciphers(
        ":".join(
            [
                "ECDHE+AESGCM",
                "ECDHE+CHACHA20",
                "DHE+AESGCM",
                "DHE+CHACHA20",
                "ECDH+AESGCM",
                "DH+AESGCM",
                "ECDH+AES",
                "DH+AES",
                "RSA+AESGCM",
                "RSA+AES",
                "!aNULL",
                "!eNULL",
                "!MD5",
                "!DSS",
            ]
        )
    )
    context.load_verify_locations(capath=cert_path)
    return context


def load_macaroon(macaroon_path: str):
    with open(macaroon_path, "rb") as f:
        macaroon_bytes = f.read()
        return macaroon_bytes.hex()


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
            raise ImportError(
                "The `lndgrpc` library must be installed to use `LndWallet`."
            )

        if purerpc is None:  # pragma: nocover
            raise ImportError(
                "The `purerpc` library must be installed to use `LndWallet`."
            )

        endpoint = getenv("LND_GRPC_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.port = int(getenv("LND_GRPC_PORT"))
        self.cert_path = getenv("LND_GRPC_CERT") or getenv("LND_CERT")

        self.macaroon_path = (
            getenv("LND_GRPC_MACAROON")
            or getenv("LND_GRPC_ADMIN_MACAROON")
            or getenv("LND_ADMIN_MACAROON")
            or getenv("LND_GRPC_INVOICE_MACAROON")
            or getenv("LND_INVOICE_MACAROON")
        )
        network = getenv("LND_GRPC_NETWORK", "mainnet")

        self.rpc = lndgrpc.LNDClient(
            f"{self.endpoint}:{self.port}",
            cert_filepath=self.cert_path,
            network=network,
            macaroon_filepath=self.macaroon_path,
        )

    async def status(self) -> StatusResponse:
        try:
            resp = self.rpc._ln_stub.ChannelBalance(ln.ChannelBalanceRequest())
        except Exception as exc:
            return StatusResponse(str(exc), 0)

        return StatusResponse(None, resp.balance * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        params: Dict = {"value": amount, "expiry": 600, "private": True}

        if description_hash:
            params["description_hash"] = description_hash  # as bytes directly
        else:
            params["memo"] = memo or ""

        try:
            req = ln.Invoice(**params)
            resp = self.rpc._ln_stub.AddInvoice(req)
        except Exception as exc:
            error_message = str(exc)
            return InvoiceResponse(False, None, None, error_message)

        checking_id = stringify_checking_id(resp.r_hash)
        payment_request = str(resp.payment_request)
        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:
        resp = self.rpc.send_payment(payment_request=bolt11)

        if resp.payment_error:
            return PaymentResponse(False, "", 0, None, resp.payment_error)

        r_hash = hashlib.sha256(resp.payment_preimage).digest()
        checking_id = stringify_checking_id(r_hash)
        fee_msat = resp.payment_route.total_fees_msat
        preimage = resp.payment_preimage.hex()
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r_hash = parse_checking_id(checking_id)
            if len(r_hash) != 32:
                raise binascii.Error
        except binascii.Error:
            # this may happen if we switch between backend wallets
            # that use different checking_id formats
            return PaymentStatus(None)

        resp = self.rpc.lookup_invoice(r_hash.hex())
        if resp.settled:
            return PaymentStatus(True)

        return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(True)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        async with purerpc.secure_channel(
            self.endpoint,
            self.port,
            get_ssl_context(self.cert_path),
        ) as channel:
            client = purerpc.Client("lnrpc.Lightning", channel)
            subscribe_invoices = client.get_method_stub(
                "SubscribeInvoices",
                purerpc.RPCSignature(
                    purerpc.Cardinality.UNARY_STREAM,
                    ln.InvoiceSubscription,
                    ln.Invoice,
                ),
            )
            macaroon = load_macaroon(self.macaroon_path)

            async for inv in subscribe_invoices(
                ln.InvoiceSubscription(),
                metadata=[("macaroon", macaroon)],
            ):
                if not inv.settled:
                    continue

                checking_id = stringify_checking_id(inv.r_hash)
                yield checking_id

        print("lost connection to lnd InvoiceSubscription, please restart lnbits.")
