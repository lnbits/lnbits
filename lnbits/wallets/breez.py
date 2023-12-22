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
            assert settings.breez_greenlight_seed, "missing Greenlight seed"
            self.breez_greenlight_seed = breez_sdk.mnemonic_to_seed(
                settings.breez_greenlight_seed
            )
            assert settings.breez_api_key, "missing Breez api key"
            self.breez_api_key = settings.breez_api_key
            assert (
                settings.breez_greenlight_invite_code
            ), "missing Greenlight invite code"
            self.breez_greenlight_invite_code = settings.breez_greenlight_invite_code

            self.config = breez_sdk.default_config(
                breez_sdk.EnvironmentType.PRODUCTION,
                self.breez_api_key,
                breez_sdk.NodeConfig.GREENLIGHT(
                    config=breez_sdk.GreenlightNodeConfig(
                        partner_credentials=None,
                        invite_code=self.breez_greenlight_invite_code,
                    )
                ),
            )

            breez_sdk_working_dir = Path(settings.lnbits_data_folder, "breez-sdk")
            breez_sdk_working_dir.mkdir(parents=True, exist_ok=True)
            self.config.working_dir = breez_sdk_working_dir.absolute().as_posix()

            self.sdk_services = breez_sdk.connect(
                self.config, self.breez_greenlight_seed, SDKListener()
            )

        async def cleanup(self):
            self.sdk_services.disconnect()

        async def status(self) -> StatusResponse:
            try:
                node_info: breez_sdk.NodeState = self.sdk_services.node_info()
            except Exception as exc:
                return StatusResponse(f"Failed to connect to breez, got: '{exc}...'", 0)

            return StatusResponse(None, int(node_info.max_payable_msat))

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

            breez_invoice: breez_sdk.ReceivePaymentResponse = (
                self.sdk_services.receive_payment(
                    breez_sdk.ReceivePaymentRequest(
                        amount * 1000,  # breez uses msat
                        memo,
                        preimage=kwargs.get("preimage"),
                        opening_fee_params=None,
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
                # report issue to Breez to improve LSP routing
                self.sdk_services.report_issue(
                    breez_sdk.ReportIssueRequest.PAYMENT_FAILURE(
                        breez_sdk.ReportPaymentFailureDetails(invoice.payment_hash)
                    )
                )
                # assume that payment failed?
                return PaymentResponse(
                    False, None, None, None, f"payment failed: {exc}"
                )

            assert not payment.pending, "payment is pending"
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
            invoice = self.sdk_services.payment_by_hash(checking_id)
            if invoice is None:
                return PaymentStatus(None)
            assert invoice.payment_type == breez_sdk.PaymentType.RECEIVED
            return PaymentStatus(True)

        async def get_payment_status(self, checking_id: str) -> PaymentStatus:
            invoice = self.sdk_services.payment_by_hash(checking_id)
            if invoice is None:
                return PaymentStatus(None)
            assert invoice.payment_type == breez_sdk.PaymentType.SENT
            if invoice.pending is False:
                return PaymentStatus(
                    True, invoice.fee_msat, invoice.details.data.payment_preimage
                )
            else:
                return PaymentStatus(None)

        async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
            while True:
                event = await breez_event_queue.get()
                if event.is_invoice_paid():
                    yield event.details.payment_hash
