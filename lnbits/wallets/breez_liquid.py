# Based on breez.py

try:
    import breez_sdk_liquid as breez_sdk  # type: ignore

    BREEZ_SDK_INSTALLED = True
except ImportError:
    BREEZ_SDK_INSTALLED = False

if not BREEZ_SDK_INSTALLED:

    class BreezLiquidSdkWallet:  # pyright: ignore
        def __init__(self):
            raise RuntimeError(
                "Breez Liquid SDK is not installed. "
                "Ask admin to run `poetry add -E breez` to install it."
            )

else:
    import asyncio
    from collections.abc import AsyncGenerator
    from pathlib import Path
    from typing import Optional

    import breez_sdk_liquid as breez_sdk  # type: ignore
    from bolt11 import decode as bolt11_decode
    from breez_sdk_liquid import PaymentDetails
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

    breez_incoming_queue: asyncio.Queue[PaymentDetails.LIGHTNING] = asyncio.Queue()
    breez_outgoing_queue: dict[str, asyncio.Queue[PaymentDetails.LIGHTNING]] = {}

    class PaymentsListener(breez_sdk.EventListener):
        def on_event(self, e: breez_sdk.SdkEvent) -> None:
            logger.debug(f"received breez sdk event: {e}")
            # TODO: when this issue is fixed:
            # https://github.com/breez/breez-sdk-liquid/issues/961
            # use breez_sdk.SdkEvent.PAYMENT_WAITING_CONFIRMATION
            if not isinstance(
                e, breez_sdk.SdkEvent.PAYMENT_SUCCEEDED
            ) or not isinstance(e.details.details, breez_sdk.PaymentDetails.LIGHTNING):
                return

            payment = e.details
            payment_details = e.details.details

            if payment.payment_type is breez_sdk.PaymentType.RECEIVE:
                breez_incoming_queue.put_nowait(payment_details)
            elif (
                payment.payment_type is breez_sdk.PaymentType.SEND
                and payment_details.payment_hash in breez_outgoing_queue
            ):
                breez_outgoing_queue[payment_details.payment_hash].put_nowait(
                    payment_details
                )

    class BreezLiquidSdkWallet(Wallet):  # type: ignore[no-redef]
        def __init__(self):
            if not settings.breez_liquid_seed:
                raise ValueError(
                    "cannot initialize BreezLiquidSdkWallet: missing breez_liquid_seed"
                )

            if not settings.breez_liquid_api_key:
                with open(Path("lnbits/wallets", ".breez")) as f:
                    settings.breez_liquid_api_key = f.read().strip()

            self.config = breez_sdk.default_config(
                breez_sdk.LiquidNetwork.MAINNET,
                breez_api_key=settings.breez_liquid_api_key,
            )

            breez_sdk_working_dir = Path(
                settings.lnbits_data_folder, "breez-liquid-sdk"
            )
            breez_sdk_working_dir.mkdir(parents=True, exist_ok=True)
            self.config.working_dir = breez_sdk_working_dir.absolute().as_posix()

            try:
                mnemonic = settings.breez_liquid_seed
                connect_request = breez_sdk.ConnectRequest(
                    config=self.config, mnemonic=mnemonic
                )
                self.sdk_services = breez_sdk.connect(connect_request)
                self.sdk_services.add_event_listener(PaymentsListener())
            except Exception as exc:
                logger.warning(exc)
                raise ValueError(
                    f"cannot initialize BreezLiquidSdkWallet: {exc!s}"
                ) from exc

        async def cleanup(self):
            self.sdk_services.disconnect()

        async def status(self) -> StatusResponse:
            try:
                info: breez_sdk.GetInfoResponse = self.sdk_services.get_info()
            except Exception as exc:
                logger.warning(exc)
                return StatusResponse(f"Failed to connect to breez, got: '{exc}...'", 0)
            return StatusResponse(None, int(info.wallet_info.balance_sat * 1000))

        async def create_invoice(
            self,
            amount: int,
            memo: Optional[str] = None,
            description_hash: Optional[bytes] = None,
            unhashed_description: Optional[bytes] = None,
            **_,
        ) -> InvoiceResponse:
            try:
                # issue with breez sdk, receive_amount is of type BITCOIN
                # not ReceiveAmount after initialisation
                receive_amount = breez_sdk.ReceiveAmount.BITCOIN(amount)
                req = self.sdk_services.prepare_receive_payment(
                    breez_sdk.PrepareReceiveRequest(
                        payment_method=breez_sdk.PaymentMethod.BOLT11_INVOICE,
                        amount=receive_amount,  # type: ignore
                    )
                )
                receive_fees_sats = req.fees_sat

                description = memo or (
                    unhashed_description.decode() if unhashed_description else ""
                )

                res = self.sdk_services.receive_payment(
                    breez_sdk.ReceivePaymentRequest(
                        prepare_response=req,
                        description=description,
                        use_description_hash=description_hash is not None,
                    )
                )

                bolt11 = res.destination
                invoice_data = bolt11_decode(bolt11)
                payment_hash = invoice_data.payment_hash

                return InvoiceResponse(
                    ok=True,
                    checking_id=payment_hash,
                    payment_request=bolt11,
                    fee_msat=receive_fees_sats * 1000,
                )
            except Exception as e:
                logger.warning(e)
                return InvoiceResponse(ok=False, error_message=str(e))

        async def pay_invoice(
            self, bolt11: str, fee_limit_msat: int
        ) -> PaymentResponse:
            invoice_data = bolt11_decode(bolt11)

            try:
                prepare_req = breez_sdk.PrepareSendRequest(destination=bolt11)
                req = self.sdk_services.prepare_send_payment(prepare_req)

                fee_limit_sat = settings.breez_liquid_fee_offset_sat + int(
                    fee_limit_msat / 1000
                )

                if req.fees_sat and req.fees_sat > fee_limit_sat:
                    return PaymentResponse(
                        ok=False,
                        error_message=(
                            f"fee of {req.fees_sat} sat exceeds limit of "
                            f"{fee_limit_sat} sat"
                        ),
                    )

                send_response = self.sdk_services.send_payment(
                    breez_sdk.SendPaymentRequest(prepare_response=req)
                )

            except Exception as exc:
                logger.warning(exc)
                return PaymentResponse(error_message=f"Exception while payment: {exc}")

            payment: breez_sdk.Payment = send_response.payment
            logger.debug(f"pay invoice res: {payment}")
            checking_id = invoice_data.payment_hash

            fees = req.fees_sat * 1000 if req.fees_sat and req.fees_sat > 0 else 0

            if payment.status != breez_sdk.PaymentState.COMPLETE:
                return await self._wait_for_outgoing_payment(checking_id, fees, 5)

            if not isinstance(payment.details, breez_sdk.PaymentDetails.LIGHTNING):
                return PaymentResponse(
                    error_message="lightning payment details are not available"
                )

            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=payment.fees_sat * 1000,
                preimage=payment.details.preimage,
            )

        async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
            try:
                req = breez_sdk.GetPaymentRequest.PAYMENT_HASH(checking_id)
                payment = self.sdk_services.get_payment(req=req)  # type: ignore
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != breez_sdk.PaymentType.RECEIVE:
                    logger.warning(f"unexpected payment type: {payment.status}")
                    return PaymentPendingStatus()
                if payment.status == breez_sdk.PaymentState.FAILED:
                    return PaymentFailedStatus()
                if payment.status == breez_sdk.PaymentState.COMPLETE:
                    return PaymentSuccessStatus(
                        paid=True, fee_msat=int(payment.fees_sat * 1000)
                    )
                return PaymentPendingStatus()
            except Exception as exc:
                logger.warning(exc)
                return PaymentPendingStatus()

        async def get_payment_status(self, checking_id: str) -> PaymentStatus:
            try:
                req = breez_sdk.GetPaymentRequest.PAYMENT_HASH(checking_id)
                payment = self.sdk_services.get_payment(req=req)  # type: ignore
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != breez_sdk.PaymentType.SEND:
                    logger.warning(f"unexpected payment type: {payment.status}")
                    return PaymentPendingStatus()
                if payment.status == breez_sdk.PaymentState.COMPLETE:
                    if not isinstance(
                        payment.details, breez_sdk.PaymentDetails.LIGHTNING
                    ):
                        logger.warning("payment details are not of type LIGHTNING")
                        return PaymentPendingStatus()
                    return PaymentSuccessStatus(
                        fee_msat=int(payment.fees_sat * 1000),
                        preimage=payment.details.preimage,
                    )
                if payment.status == breez_sdk.PaymentState.FAILED:
                    return PaymentFailedStatus()
                return PaymentPendingStatus()
            except Exception as exc:
                logger.warning(exc)
                return PaymentPendingStatus()

        async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
            while settings.lnbits_running:
                details = await breez_incoming_queue.get()
                logger.debug(f"breez invoice paid event: {details}")
                if not details.invoice:
                    logger.warning(
                        "Paid invoices stream expected bolt11 invoice, got None"
                    )
                    continue

                invoice_data = bolt11_decode(details.invoice)
                yield invoice_data.payment_hash

        async def _wait_for_outgoing_payment(
            self, checking_id: str, fees: int, timeout: int
        ) -> PaymentResponse:
            try:
                breez_outgoing_queue[checking_id] = asyncio.Queue()
                payment_details = await asyncio.wait_for(
                    breez_outgoing_queue[checking_id].get(), timeout
                )
                return PaymentResponse(
                    ok=True,
                    preimage=payment_details.preimage,
                    checking_id=checking_id,
                    fee_msat=fees,
                )
            except asyncio.TimeoutError:
                logger.debug(
                    f"payment '{checking_id}' is still pending after {timeout} seconds"
                )
                return PaymentResponse(
                    checking_id=checking_id,
                    fee_msat=fees,
                    error_message="payment is pending",
                )
            finally:
                breez_outgoing_queue.pop(checking_id, None)
