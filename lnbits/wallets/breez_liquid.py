# Based on breez.py

try:
    import breez_sdk_liquid as breez_sdk  # type: ignore

    BREEZ_SDK_INSTALLED = True
except ImportError:
    BREEZ_SDK_INSTALLED = False

if not BREEZ_SDK_INSTALLED:

    class BreezSdkWallet:  # pyright: ignore
        def __init__(self):
            raise RuntimeError(
                "Breez Liquid SDK is not installed. "
                "Ask admin to run `poetry add -E breez_sdk_liquid` to install it."
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
        PaymentFailedStatus,
        PaymentPendingStatus,
        PaymentResponse,
        PaymentSuccessStatus,
        StatusResponse,
        UnsupportedError,
        Wallet,
    )

    breez_event_queue: asyncio.Queue = asyncio.Queue()

    class SDKListener(
        breez_sdk.EventListener  # pyright: ignore[reportUnboundVariable]
    ):
        def on_event(self, event):
            breez_event_queue.put_nowait(event)

    class BreezLiquidSdkWallet(Wallet):  # type: ignore[no-redef]
        def __init__(self):
            if not settings.breez_mnemonic:
                raise ValueError(
                    "cannot initialize BreezLiquidSdkWallet: missing breez_mnemonic"
                )

            self.config = breez_sdk.default_config(breez_sdk.LiquidNetwork.MAINNET)

            breez_sdk_working_dir = Path(
                settings.lnbits_data_folder, "breez-liquid-sdk"
            )
            breez_sdk_working_dir.mkdir(parents=True, exist_ok=True)
            self.config.working_dir = breez_sdk_working_dir.absolute().as_posix()

            try:
                mnemonic = settings.breez_mnemonic
                connect_request = breez_sdk.ConnectRequest(self.config, mnemonic)
                self.sdk_services = breez_sdk.connect(connect_request)
                self.sdk_services.add_event_listener(SDKListener())
            except Exception as exc:
                logger.warning(exc)
                raise ValueError(f"cannot initialize BreezSdkWallet: {exc!s}") from exc

        async def cleanup(self):
            self.sdk_services.disconnect()

        async def status(self) -> StatusResponse:
            try:
                info: breez_sdk.GetInfoResponse = self.sdk_services.get_info()
            except Exception as exc:
                return StatusResponse(f"Failed to connect to breez, got: '{exc}...'", 0)
            return StatusResponse(None, int(info.balance_sat * 1000))

        async def create_invoice(
            self,
            amount: int,
            memo: Optional[str] = None,
            description_hash: Optional[bytes] = None,
            unhashed_description: Optional[bytes] = None,
            **kwargs,
        ) -> InvoiceResponse:
            try:
                if description_hash and not unhashed_description:
                    raise UnsupportedError(
                        "'description_hash' unsupported by Greenlight, provide"
                        " 'unhashed_description'"
                    )

                res: breez_sdk.ReceivePaymentResponse = (
                    self.sdk_services.receive_payment(
                        breez_sdk.ReceivePaymentRequest(
                            self.sdk_services.prepare_receive_payment(
                                breez_sdk.PrepareReceiveRequest(
                                    int(amount), breez_sdk.PaymentMethod.LIGHTNING
                                )
                            ),
                            (
                                unhashed_description.decode()
                                if unhashed_description
                                else memo
                            ),
                            description_hash is not None,
                        )
                    )
                )

                bolt11 = res.destination
                invoice_data = lnbits_bolt11.decode(bolt11)
                payment_hash = invoice_data.payment_hash

                return InvoiceResponse(
                    True,
                    payment_hash,
                    bolt11,
                    None,
                )
            except Exception as e:
                logger.warning(e)
                return InvoiceResponse(False, None, None, str(e))

        async def pay_invoice(
            self, bolt11: str, fee_limit_msat: int
        ) -> PaymentResponse:
            invoice_data = lnbits_bolt11.decode(bolt11)

            try:

                send_response = self.sdk_services.send_payment(
                    breez_sdk.SendPaymentRequest(
                        self.sdk_services.prepare_send_payment(
                            breez_sdk.PrepareSendRequest(
                                bolt11,
                                int(
                                    invoice_data.amount_msat / 1000
                                    if invoice_data.amount_msat
                                    else 0
                                ),
                            )
                        )
                    )
                )
                payment: breez_sdk.Payment = send_response.payment

            except Exception as exc:
                logger.warning(exc)
                # assume that payment failed?
                return PaymentResponse(
                    False, None, None, None, f"payment failed: {exc}"
                )

            if payment.status != breez_sdk.PaymentState.COMPLETE:
                return PaymentResponse(False, None, None, None, "payment is pending")

            # let's use the payment_hash as the checking_id
            checking_id = invoice_data.payment_hash
            lightning_details: breez_sdk.PaymentDetails.LIGHTNING = payment.details
            return PaymentResponse(
                True,
                checking_id,
                payment.fees_sat * 1000,
                lightning_details.preimage,
                None,
            )

        def _find_payment(self, payment_hash: str) -> Optional[breez_sdk.Payment]:
            offset = 0
            while True:
                history: breez_sdk.Payment = self.sdk_services.list_payments(
                    breez_sdk.ListPaymentsRequest(offset=0, limit=100)
                )
                for p in history:
                    details: breez_sdk.PaymentDetails = p.details
                    if not details or not details.is_lightning():
                        continue
                    lightning_details: breez_sdk.PaymentDetails.LIGHTNING = details
                    invoice_data = lnbits_bolt11.decode(lightning_details.bolt11)
                    if invoice_data.payment_hash == payment_hash:
                        return p
                if len(history) < 100:
                    break
                offset += 100
            return None

        async def get_invoice_status(self, checking_id: str) -> breez_sdk.PaymentState:
            try:
                payment: breez_sdk.Payment = self._find_payment(checking_id)
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != breez_sdk.PaymentType.RECEIVE:
                    logger.warning(f"unexpected payment type: {payment.status}")
                    return PaymentPendingStatus()
                if payment.status == breez_sdk.PaymentState.FAILED:
                    return PaymentFailedStatus()
                if payment.status == breez_sdk.PaymentState.COMPLETE:
                    return PaymentSuccessStatus()
                return PaymentPendingStatus()
            except Exception as exc:
                logger.warning(exc)
                return PaymentPendingStatus()

        async def get_payment_status(self, checking_id: str) -> breez_sdk.PaymentState:
            try:
                payment: breez_sdk.Payment = self._find_payment(checking_id)
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != breez_sdk.PaymentType.SEND:
                    logger.warning(f"unexpected payment type: {payment.status}")
                    return PaymentPendingStatus()
                if payment.status == breez_sdk.PaymentState.COMPLETE:
                    lightning_details: breez_sdk.PaymentDetails.LIGHTNING = (
                        payment.details
                    )
                    return PaymentSuccessStatus(
                        fee_msat=int(payment.fees_sat * 1000),
                        preimage=lightning_details.preimage,
                    )
                if payment.status == breez_sdk.PaymentStatus.FAILED:
                    return PaymentFailedStatus()
                return PaymentPendingStatus()
            except Exception as exc:
                logger.warning(exc)
                return PaymentPendingStatus()

        async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
            while True:
                event = await breez_event_queue.get()
                if event.is_invoice_paid():
                    yield event.details.payment_hash
