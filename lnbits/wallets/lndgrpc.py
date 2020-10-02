try:
    import lnd_grpc  # type: ignore
except ImportError:  # pragma: nocover
    lnd_grpc = None

import base64
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
        if lnd_grpc is None:  # pragma: nocover
            raise ImportError("The `lnd-grpc` library must be installed to use `LndWallet`.")

        endpoint = getenv("LND_GRPC_ENDPOINT")
        endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        port = getenv("LND_GRPC_PORT")
        cert = getenv("LND_GRPC_CERT") or getenv("LND_CERT")
        auth_admin = getenv("LND_ADMIN_MACAROON")
        auth_invoices = getenv("LND_INVOICE_MACAROON")
        network = getenv("LND_GRPC_NETWORK", "mainnet")

        self.admin_rpc = lnd_grpc.Client(
            lnd_dir=None,
            macaroon_path=auth_admin,
            tls_cert_path=cert,
            network=network,
            grpc_host=endpoint,
            grpc_port=port,
        )

        self.invoices_rpc = lnd_grpc.Client(
            lnd_dir=None,
            macaroon_path=auth_invoices,
            tls_cert_path=cert,
            network=network,
            grpc_host=endpoint,
            grpc_port=port,
        )

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        params: Dict = {"value": amount, "expiry": 600, "private": True}
        if description_hash:
            params["description_hash"] = description_hash  # as bytes directly
        else:
            params["memo"] = memo or ""
        resp = self.invoices_rpc.add_invoice(**params)

        checking_id = stringify_checking_id(resp.r_hash)
        payment_request = str(resp.payment_request)
        return InvoiceResponse(True, checking_id, payment_request, None)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        resp = self.admin_rpc.pay_invoice(payment_request=bolt11)

        if resp.payment_error:
            return PaymentResponse(False, "", 0, resp.payment_error)

        checking_id = stringify_checking_id(resp.payment_hash)
        return PaymentResponse(True, checking_id, 0, None)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r_hash = parse_checking_id(checking_id)
        for _response in self.invoices_rpc.subscribe_single_invoice(r_hash):
            if _response.state == 1:
                return PaymentStatus(True)

        return PaymentStatus(None)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(True)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        for paid in self.invoices_rpc.SubscribeInvoices():
            print("PAID", paid)
            checking_id = stringify_checking_id(paid.r_hash)
            yield checking_id
