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
    from loguru import logger

    from lnbits import bolt11 as lnbits_bolt11
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

    breez_event_queue: asyncio.Queue[breez_sdk.SdkEvent] = asyncio.Queue()

    class SDKListener(breez_sdk.EventListener):
        def on_event(self, e: breez_sdk.SdkEvent) -> None:
            logger.debug(f"received breez sdk event: {e}")
            breez_event_queue.put_nowait(e)

    class BreezLiquidSdkWallet(Wallet):  # type: ignore[no-redef]
        def __init__(self):
            if not settings.breez_liquid_seed:
                raise ValueError(
                    "cannot initialize BreezLiquidSdkWallet: missing breez_liquid_seed"
                )

            if not settings.breez_liquid_api_key:
                raise ValueError(
                    "cannot initialize BreezLiquidSdkWallet: "
                    "missing breez_liquid_api_key"
                )

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
                self.sdk_services.add_event_listener(SDKListener())
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
                # TODO: issue with breez sdk, receive_amount is of type BITCOIN
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
                invoice_data = lnbits_bolt11.decode(bolt11)
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
            invoice_data = lnbits_bolt11.decode(bolt11)

            try:
                prepare_req = breez_sdk.PrepareSendRequest(destination=bolt11)
                req = self.sdk_services.prepare_send_payment(prepare_req)

                # TODO figure out the fee madness for breez liquid and phoenixd
                fee_limit_sat = 50 + int(fee_limit_msat / 1000)

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
                # assume that payment failed?
                return PaymentResponse(ok=False, error_message=f"payment failed: {exc}")

            payment: breez_sdk.Payment = send_response.payment
            checking_id = invoice_data.payment_hash

            fees = req.fees_sat * 1000 if req.fees_sat and req.fees_sat > 0 else 0

            if payment.status != breez_sdk.PaymentState.COMPLETE:
                return PaymentResponse(
                    checking_id=checking_id,
                    fee_msat=fees,
                    error_message="payment is pending",
                )

            if not isinstance(payment.details, breez_sdk.PaymentDetails.LIGHTNING):
                return PaymentResponse(
                    error_message="lightning payment details are not available"
                )

            # let's use the payment_hash as the checking_id
            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=payment.fees_sat * 1000,
                preimage=payment.details.preimage,
            )

        def _find_payment(self, payment_hash: str) -> Optional[breez_sdk.Payment]:
            offset = 0
            while True:
                list_payments_request = breez_sdk.ListPaymentsRequest(
                    offset=offset, limit=100
                )
                history: list[breez_sdk.Payment] = self.sdk_services.list_payments(
                    req=list_payments_request
                )
                for p in history:
                    if (
                        not p.details
                        or not p.details.is_lightning()
                        or not isinstance(p.details, breez_sdk.PaymentDetails.LIGHTNING)
                        or not p.details.invoice
                    ):
                        continue
                    invoice_data = lnbits_bolt11.decode(p.details.invoice)
                    if invoice_data.payment_hash == payment_hash:
                        return p
                if len(history) < 100:
                    break
                offset += 100
            return None

        async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
            try:
                payment = self._find_payment(checking_id)
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
                payment = self._find_payment(checking_id)
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
                event = await breez_event_queue.get()
                # you can set success of we hit `PAYMENT_WAITING_CONFIRMATION`
                # instead of `PAYMENT_SUCCEEDED` to make is faster
                # https://github.com/breez/breez-sdk-liquid/issues/961
                # uncomment if this issue is resolved (duplicate events)
                # if not isinstance(
                #     event, breez_sdk.SdkEvent.PAYMENT_WAITING_CONFIRMATION
                # ) and
                if not isinstance(event, breez_sdk.SdkEvent.PAYMENT_SUCCEEDED):
                    continue
                logger.debug(f"breez invoice paid event: {event.details}")
                details = event.details.details
                if (
                    not details
                    or not isinstance(details, breez_sdk.PaymentDetails.LIGHTNING)
                    or not details.invoice
                ):
                    continue
                invoice_data = lnbits_bolt11.decode(details.invoice)
                yield invoice_data.payment_hash
