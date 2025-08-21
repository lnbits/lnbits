import base64
from importlib.util import find_spec

from lnbits.exceptions import UnsupportedError

if not find_spec("breez_sdk"):

    class BreezSdkWallet:  # pyright: ignore
        def __init__(self):
            raise RuntimeError(
                "Breez SDK is not installed. "
                "Ask admin to run `uv sync --extra breez` to install it."
            )

else:
    import asyncio
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from bolt11 import Bolt11Exception
    from bolt11 import decode as bolt11_decode
    from breez_sdk import (
        BreezEvent,
        ConnectRequest,
        EnvironmentType,
        EventListener,
        GreenlightCredentials,
        GreenlightNodeConfig,
        NodeConfig,
        PaymentDetails,
        PaymentType,
        ReceivePaymentRequest,
        ReceivePaymentResponse,
        ReportIssueRequest,
        ReportPaymentFailureDetails,
        SendPaymentRequest,
        SendPaymentResponse,
        connect,
        default_config,
        mnemonic_to_seed,
    )
    from breez_sdk import PaymentStatus as BreezPaymentStatus
    from loguru import logger

    from lnbits.settings import settings

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

    breez_incoming_queue: asyncio.Queue[PaymentDetails.LN] = asyncio.Queue()

    class PaymentsListener(EventListener):
        def on_event(self, e: BreezEvent) -> None:
            logger.debug(f"received breez sdk event: {e}")
            if isinstance(e, BreezEvent.PAYMENT_SUCCEED) and isinstance(
                e.details, PaymentDetails.LN
            ):
                breez_incoming_queue.put_nowait(e.details)

    def load_bytes(source: str, extension: str) -> bytes | None:
        # first check if it can be read from a file
        if source.split(".")[-1] == extension:
            with open(source, "rb") as f:
                source_bytes = f.read()
                return source_bytes
        else:
            # else check the source string can be converted from hex
            try:
                return bytes.fromhex(source)
            except ValueError:
                pass
            # else convert from base64
            try:
                return base64.b64decode(source)
            except Exception as exc:
                logger.debug(exc)
        return None

    def load_greenlight_credentials() -> GreenlightCredentials | None:
        if (
            settings.breez_greenlight_device_key
            and settings.breez_greenlight_device_cert
        ):
            device_key_bytes = load_bytes(settings.breez_greenlight_device_key, "pem")
            device_cert_bytes = load_bytes(settings.breez_greenlight_device_cert, "crt")
            if not device_key_bytes or not device_cert_bytes:
                raise ValueError(
                    "cannot initialize BreezSdkWallet: "
                    "cannot decode breez_greenlight_device_key "
                    "or breez_greenlight_device_cert"
                )
            return GreenlightCredentials(
                developer_key=list(device_key_bytes),
                developer_cert=list(device_cert_bytes),
            )
        return None

    class BreezSdkWallet(Wallet):  # type: ignore[no-redef]
        def __init__(self):
            if not settings.breez_greenlight_seed:
                raise ValueError(
                    "cannot initialize BreezSdkWallet: missing breez_greenlight_seed"
                )
            if not settings.breez_api_key:
                raise ValueError(
                    "cannot initialize BreezSdkWallet: missing breez_api_key"
                )
            if (
                settings.breez_greenlight_device_key
                and not settings.breez_greenlight_device_cert
            ):
                raise ValueError(
                    "cannot initialize BreezSdkWallet: "
                    "missing breez_greenlight_device_cert"
                )
            if (
                settings.breez_greenlight_device_cert
                and not settings.breez_greenlight_device_key
            ):
                raise ValueError(
                    "cannot initialize BreezSdkWallet: "
                    "missing breez_greenlight_device_key"
                )

            gl_config = GreenlightNodeConfig(
                partner_credentials=load_greenlight_credentials(),
                invite_code=settings.breez_greenlight_invite_code,
            )
            node_config = NodeConfig.GREENLIGHT(config=gl_config)
            self.config = default_config(
                EnvironmentType.PRODUCTION,
                settings.breez_api_key,
                node_config=node_config,  # type: ignore[arg-type]
            )

            breez_sdk_working_dir = Path(settings.lnbits_data_folder, "breez-sdk")
            breez_sdk_working_dir.mkdir(parents=True, exist_ok=True)
            self.config.working_dir = breez_sdk_working_dir.absolute().as_posix()

            try:
                seed = mnemonic_to_seed(settings.breez_greenlight_seed)
                connect_request = ConnectRequest(config=self.config, seed=seed)
                self.sdk_services = connect(connect_request, PaymentsListener())
            except Exception as exc:
                logger.warning(exc)
                raise ValueError(f"cannot initialize BreezSdkWallet: {exc!s}") from exc

        async def cleanup(self):
            self.sdk_services.disconnect()

        async def status(self) -> StatusResponse:
            try:
                node_info = self.sdk_services.node_info()
            except Exception as exc:
                return StatusResponse(f"Failed to connect to breez, got: '{exc}...'", 0)

            return StatusResponse(None, int(node_info.channels_balance_msat))

        async def create_invoice(
            self,
            amount: int,
            memo: str | None = None,
            description_hash: bytes | None = None,
            unhashed_description: bytes | None = None,
            **kwargs,
        ) -> InvoiceResponse:
            # if description_hash or unhashed_description:
            #     raise UnsupportedError("description_hash and unhashed_description")
            try:
                if description_hash and not unhashed_description:
                    raise UnsupportedError(
                        "'description_hash' unsupported by Greenlight, provide"
                        " 'unhashed_description'"
                    )
                breez_invoice: ReceivePaymentResponse = (
                    self.sdk_services.receive_payment(
                        ReceivePaymentRequest(
                            amount_msat=amount * 1000,  # breez uses msat
                            description=(
                                unhashed_description.decode()
                                if unhashed_description
                                else memo or ""
                            ),
                            preimage=kwargs.get("preimage"),
                            opening_fee_params=None,
                            use_description_hash=True if unhashed_description else None,
                        )
                    )
                )

                # TODO: add preimage
                return InvoiceResponse(
                    ok=True,
                    checking_id=breez_invoice.ln_invoice.payment_hash,
                    payment_request=breez_invoice.ln_invoice.bolt11,
                    # preimage=breez_invoice.ln_invoice.payment_preimage,
                )
            except Exception as e:
                logger.warning(e)
                return InvoiceResponse(ok=False, error_message=str(e))

        async def pay_invoice(
            self, bolt11: str, fee_limit_msat: int
        ) -> PaymentResponse:
            logger.debug(f"fee_limit_msat {fee_limit_msat} is ignored by Breez SDK")
            try:
                invoice = bolt11_decode(bolt11)
            except Bolt11Exception as exc:
                logger.warning(exc)
                return PaymentResponse(
                    ok=False, error_message=f"invalid bolt11 invoice: {exc}"
                )
            try:
                send_payment_request = SendPaymentRequest(
                    bolt11=bolt11, use_trampoline=settings.breez_use_trampoline
                )
                send_payment_response: SendPaymentResponse = (
                    self.sdk_services.send_payment(send_payment_request)
                )
                payment = send_payment_response.payment
            except Exception as exc:
                logger.warning(exc)
                try:
                    # report issue to Breez to improve LSP routing
                    payment_error = ReportIssueRequest.PAYMENT_FAILURE(
                        ReportPaymentFailureDetails(payment_hash=invoice.payment_hash)
                    )
                    self.sdk_services.report_issue(payment_error)  # type: ignore[arg-type]
                except Exception as ex:
                    logger.info(ex)
                return PaymentResponse(error_message=f"exception while payment {exc!s}")

            if payment.status != BreezPaymentStatus.COMPLETE:
                return PaymentResponse(ok=None, error_message="payment is pending")

            # let's use the payment_hash as the checking_id
            checking_id = invoice.payment_hash

            if not isinstance(payment.details, PaymentDetails.LN):
                return PaymentResponse(
                    error_message="Breez SDK returned a non-LN payment details object",
                )

            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=payment.fee_msat,
                preimage=payment.details.data.payment_preimage,
            )

        async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
            try:
                payment = self.sdk_services.payment_by_hash(checking_id)
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != PaymentType.RECEIVED:
                    logger.warning(f"unexpected payment type: {payment.status}")
                    return PaymentPendingStatus()
                if not isinstance(payment.details, PaymentDetails.LN):
                    logger.warning(f"unexpected paymentdetails type: {payment.details}")
                    return PaymentPendingStatus()
                if payment.status == BreezPaymentStatus.FAILED:
                    return PaymentFailedStatus()
                if payment.status == BreezPaymentStatus.COMPLETE:
                    return PaymentSuccessStatus(
                        fee_msat=payment.fee_msat,
                        preimage=payment.details.data.payment_preimage,
                    )
                return PaymentPendingStatus()
            except Exception as exc:
                logger.warning(exc)
                return PaymentPendingStatus()

        async def get_payment_status(self, checking_id: str) -> PaymentStatus:
            try:
                payment = self.sdk_services.payment_by_hash(checking_id)
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != PaymentType.SENT:
                    logger.warning(f"unexpected payment type: {payment.payment_type}")
                    return PaymentPendingStatus()
                if not isinstance(payment.details, PaymentDetails.LN):
                    logger.warning(f"unexpected paymentdetails type: {payment.details}")
                    return PaymentPendingStatus()
                if payment.status == BreezPaymentStatus.COMPLETE:
                    return PaymentSuccessStatus(
                        fee_msat=payment.fee_msat,
                        preimage=payment.details.data.payment_preimage,
                    )
                if payment.status == BreezPaymentStatus.FAILED:
                    return PaymentFailedStatus()
                return PaymentPendingStatus()
            except Exception as exc:
                logger.warning(exc)
                return PaymentPendingStatus()

        async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
            while settings.lnbits_running:
                details = await breez_incoming_queue.get()
                yield details.data.payment_hash
