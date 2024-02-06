try:
    import breez_sdk  # type: ignore

    BREEZ_SDK_INSTALLED = True
except ImportError:
    BREEZ_SDK_INSTALLED = False

if not BREEZ_SDK_INSTALLED:

    class BreezSdkWallet:  # pyright: ignore
        def __init__(self):
            raise RuntimeError(
                "Breez SDK is not installed. "
                "Ask admin to run `poetry install -E breez` to install it."
            )

else:
    import asyncio
    from pathlib import Path
    from typing import AsyncGenerator, Optional

    from loguru import logger

    from lnbits import bolt11 as lnbits_bolt11
    from lnbits.settings import settings

    from .base import (
        InvoiceResponse,
        PaymentResponse,
        PaymentStatus,
        StatusResponse,
        Unsupported,
        Wallet,
    )

    breez_event_queue: asyncio.Queue = asyncio.Queue()

    class SDKListener(
        breez_sdk.EventListener  # pyright: ignore[reportUnboundVariable]
    ):
        def on_event(self, event):
            logger.debug(event)
            breez_event_queue.put_nowait(event)

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
            if not settings.breez_greenlight_invite_code:
                raise ValueError(
                    "cannot initialize BreezSdkWallet: "
                    "missing breez_greenlight_invite_code"
                )

            self.config = breez_sdk.default_config(
                breez_sdk.EnvironmentType.PRODUCTION,
                settings.breez_api_key,
                breez_sdk.NodeConfig.GREENLIGHT(
                    config=breez_sdk.GreenlightNodeConfig(
                        partner_credentials=None,
                        invite_code=settings.breez_greenlight_invite_code,
                    )
                ),
            )

            breez_sdk_working_dir = Path(settings.lnbits_data_folder, "breez-sdk")
            breez_sdk_working_dir.mkdir(parents=True, exist_ok=True)
            self.config.working_dir = breez_sdk_working_dir.absolute().as_posix()

            seed = breez_sdk.mnemonic_to_seed(settings.breez_greenlight_seed)
            self.sdk_services = breez_sdk.connect(self.config, seed, SDKListener())

        async def cleanup(self):
            self.sdk_services.disconnect()

        async def status(self) -> StatusResponse:
            try:
                node_info: breez_sdk.NodeState = self.sdk_services.node_info()
            except Exception as exc:
                return StatusResponse(f"Failed to connect to breez, got: '{exc}...'", 0)

            return StatusResponse(None, int(node_info.channels_balance_msat))

        async def create_invoice(
            self,
            amount: int,
            memo: Optional[str] = None,
            description_hash: Optional[bytes] = None,
            unhashed_description: Optional[bytes] = None,
            **kwargs,
        ) -> InvoiceResponse:
            # if description_hash or unhashed_description:
            #     raise Unsupported("description_hash and unhashed_description")

            if description_hash and not unhashed_description:
                raise Unsupported(
                    "'description_hash' unsupported by Greenlight, provide"
                    " 'unhashed_description'"
                )
            breez_invoice: breez_sdk.ReceivePaymentResponse = (
                self.sdk_services.receive_payment(
                    breez_sdk.ReceivePaymentRequest(
                        amount * 1000,  # breez uses msat
                        unhashed_description.decode() if unhashed_description else memo,
                        preimage=kwargs.get("preimage"),
                        opening_fee_params=None,
                        use_description_hash=True if unhashed_description else None,
                    )
                )
            )

            return InvoiceResponse(
                True,
                breez_invoice.ln_invoice.payment_hash,
                breez_invoice.ln_invoice.bolt11,
                None,
            )

        async def pay_invoice(
            self, bolt11: str, fee_limit_msat: int
        ) -> PaymentResponse:
            invoice = lnbits_bolt11.decode(bolt11)

            try:
                req = breez_sdk.SendPaymentRequest(bolt11=bolt11)
                payment: breez_sdk.Payment = self.sdk_services.send_payment(req)
            except Exception as exc:
                logger.info(exc)
                try:
                    # try to report issue to Breez to improve LSP routing
                    self.sdk_services.report_issue(
                        breez_sdk.ReportIssueRequest.PAYMENT_FAILURE(
                            breez_sdk.ReportPaymentFailureDetails(invoice.payment_hash)
                        )
                    )
                except Exception as ex:
                    logger.info(ex)
                # assume that payment failed?
                return PaymentResponse(
                    False, None, None, None, f"payment failed: {exc}"
                )

            assert (
                payment.status == breez_sdk.PaymentStatus.COMPLETE
            ), "payment is pending"
            # let's use the payment_hash as the checking_id
            checking_id = invoice.payment_hash

            return PaymentResponse(
                True,
                checking_id,
                payment.fee_msat,
                payment.details.data.payment_preimage,
                None,
            )

        async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
            payment = self.sdk_services.payment_by_hash(checking_id)
            if payment is None:
                return PaymentStatus(None)
            assert payment.payment_type == breez_sdk.PaymentType.RECEIVED
            return PaymentStatus(payment.status == breez_sdk.PaymentStatus.COMPLETE)

        async def get_payment_status(self, checking_id: str) -> PaymentStatus:
            payment = self.sdk_services.payment_by_hash(checking_id)
            if payment is None:
                return PaymentStatus(None)
            assert payment.payment_type == breez_sdk.PaymentType.SENT
            if payment.status == breez_sdk.PaymentStatus.COMPLETE:
                return PaymentStatus(
                    True, payment.fee_msat, payment.details.data.payment_preimage
                )
            elif payment.status == breez_sdk.PaymentStatus.FAILED:
                return PaymentStatus(False)
            else:
                return PaymentStatus(None)

        async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
            while True:
                event = await breez_event_queue.get()
                if event.is_invoice_paid():
                    yield event.details.payment_hash
