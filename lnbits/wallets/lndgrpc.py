import base64
import lnd_grpc  # type: ignore

from os import getenv

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet


class LndWallet(Wallet):
    def __init__(self):
        endpoint = getenv("LND_GRPC_ENDPOINT")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.port = getenv("LND_GRPC_PORT")
        self.auth_admin = getenv("LND_ADMIN_MACAROON")
        self.auth_invoice = getenv("LND_INVOICE_MACAROON")
        self.auth_read = getenv("LND_READ_MACAROON")
        self.auth_cert = getenv("LND_CERT")

        lnd_rpc = lnd_grpc.Client(
            lnd_dir=None, tls_cert_path=self.auth_cert, network="mainnet", grpc_host=self.endpoint, grpc_port=self.port
        )

    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        lnd_rpc = lnd_grpc.Client(
            lnd_dir=None,
            macaroon_path=self.auth_invoice,
            tls_cert_path=self.auth_cert,
            network="mainnet",
            grpc_host=self.endpoint,
            grpc_port=self.port,
        )

        lndResponse = lnd_rpc.add_invoice(memo=memo, value=amount, expiry=600, private=True)
        decoded_hash = base64.b64encode(lndResponse.r_hash).decode("utf-8").replace("/", "_")
        print(lndResponse.r_hash)
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
