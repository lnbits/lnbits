try:
    import lnd_grpc  # type: ignore
except ImportError:  # pragma: nocover
    lnd_grpc = None

import base64
from os import getenv
from typing import Optional, Dict

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LndWallet(Wallet):
    def __init__(self):
        if lnd_grpc is None:  # pragma: nocover
            raise ImportError("The `lnd-grpc` library must be installed to use `LndWallet`.")

        endpoint = getenv("LND_GRPC_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.port = getenv("LND_GRPC_PORT")
        self.auth_admin = getenv("LND_ADMIN_MACAROON")
        self.auth_invoice = getenv("LND_INVOICE_MACAROON")
        self.auth_read = getenv("LND_READ_MACAROON")
        self.auth_cert = getenv("LND_CERT")

    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        lnd_rpc = lnd_grpc.Client(
            lnd_dir=None,
            macaroon_path=self.auth_invoice,
            tls_cert_path=self.auth_cert,
            network="mainnet",
            grpc_host=self.endpoint,
            grpc_port=self.port,
        )

        params: Dict = {"value": amount, "expiry": 600, "private": True}
        if description_hash:
            params["description_hash"] = description_hash  # as bytes directly
        else:
            params["memo"] = memo or ""
        lndResponse = lnd_rpc.add_invoice(**params)
        decoded_hash = base64.b64encode(lndResponse.r_hash).decode("utf-8").replace("/", "_")
        ok, checking_id, payment_request, error_message = True, decoded_hash, str(lndResponse.payment_request), None
        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        lnd_rpc = lnd_grpc.Client(
            lnd_dir=None,
            macaroon_path=self.auth_admin,
            tls_cert_path=self.auth_cert,
            network="mainnet",
            grpc_host=self.endpoint,
            grpc_port=self.port,
        )

        payinvoice = lnd_rpc.pay_invoice(payment_request=bolt11,)

        ok, checking_id, fee_msat, error_message = True, None, 0, None

        if payinvoice.payment_error:
            ok, error_message = False, payinvoice.payment_error
        else:
            checking_id = base64.b64encode(payinvoice.payment_hash).decode("utf-8").replace("/", "_")

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:

        check_id = base64.b64decode(checking_id.replace("_", "/"))
        print(check_id)
        lnd_rpc = lnd_grpc.Client(
            lnd_dir=None,
            macaroon_path=self.auth_invoice,
            tls_cert_path=self.auth_cert,
            network="mainnet",
            grpc_host=self.endpoint,
            grpc_port=self.port,
        )

        for _response in lnd_rpc.subscribe_single_invoice(check_id):
            if _response.state == 1:
                return PaymentStatus(True)

        return PaymentStatus(None)

    def get_payment_status(self, checking_id: str) -> PaymentStatus:

        return PaymentStatus(True)
