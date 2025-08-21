# Based on breez.py

from importlib.util import find_spec

if not find_spec("breez_sdk_liquid"):

    class BreezLiquidSdkWallet:  # pyright: ignore
        def __init__(self):
            raise RuntimeError(
                "Breez Liquid SDK is not installed. "
                "Ask admin to run `uv sync --extra breez` to install it."
            )

else:
    import asyncio
    from asyncio import Queue
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from bolt11 import decode as bolt11_decode
    from breez_sdk_liquid import (
        ConnectRequest,
        EventListener,
        GetInfoResponse,
        GetPaymentRequest,
        LiquidNetwork,
        Payment,
        PaymentDetails,
        PaymentMethod,
        PaymentState,
        PaymentType,
        PrepareReceiveRequest,
        PrepareSendRequest,
        ReceiveAmount,
        ReceivePaymentRequest,
        SdkEvent,
        SendPaymentRequest,
        connect,
        default_config,
    )
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

    breez_incoming_queue: Queue[PaymentDetails.LIGHTNING] = Queue()
    breez_outgoing_queue: dict[str, Queue[PaymentDetails.LIGHTNING]] = {}

    class PaymentsListener(EventListener):
        def on_event(self, e: SdkEvent) -> None:
            logger.debug(f"received breez sdk event: {e}")
            # TODO: when this issue is fixed:
            # https://github.com/breez/breez-sdk-liquid/issues/961
            # use SdkEvent.PAYMENT_WAITING_CONFIRMATION
            if not isinstance(e, SdkEvent.PAYMENT_SUCCEEDED) or not isinstance(
                e.details.details, PaymentDetails.LIGHTNING
            ):
                return

            payment = e.details
            payment_details = e.details.details

            if payment.payment_type is PaymentType.RECEIVE:
                breez_incoming_queue.put_nowait(payment_details)
            elif (
                payment.payment_type is PaymentType.SEND
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

            self.config = default_config(
                LiquidNetwork.MAINNET,
                breez_api_key=settings.breez_liquid_api_key,
            )

            breez_sdk_working_dir = Path(
                settings.lnbits_data_folder, "breez-liquid-sdk"
            )
            breez_sdk_working_dir.mkdir(parents=True, exist_ok=True)
            self.config.working_dir = breez_sdk_working_dir.absolute().as_posix()

            try:
                mnemonic = settings.breez_liquid_seed
                connect_request = ConnectRequest(config=self.config, mnemonic=mnemonic)
                self.sdk_services = connect(connect_request)
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
                info: GetInfoResponse = self.sdk_services.get_info()
            except Exception as exc:
                logger.warning(exc)
                return StatusResponse(f"Failed to connect to breez, got: '{exc}...'", 0)
            return StatusResponse(None, int(info.wallet_info.balance_sat * 1000))

        async def create_invoice(
            self,
            amount: int,
            memo: str | None = None,
            description_hash: bytes | None = None,
            unhashed_description: bytes | None = None,
            **_,
        ) -> InvoiceResponse:
            try:
                # issue with breez sdk, receive_amount is of type BITCOIN
                # not ReceiveAmount after initialisation
                receive_amount = ReceiveAmount.BITCOIN(amount)
                req = self.sdk_services.prepare_receive_payment(
                    PrepareReceiveRequest(
                        payment_method=PaymentMethod.BOLT11_INVOICE,
                        amount=receive_amount,  # type: ignore
                    )
                )
                receive_fees_sats = req.fees_sat

                description = memo or (
                    unhashed_description.decode() if unhashed_description else ""
                )

                res = self.sdk_services.receive_payment(
                    ReceivePaymentRequest(
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
                prepare_req = PrepareSendRequest(destination=bolt11)
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
                    SendPaymentRequest(prepare_response=req)
                )

            except Exception as exc:
                logger.warning(exc)
                return PaymentResponse(error_message=f"Exception while payment: {exc}")

            payment: Payment = send_response.payment
            logger.debug(f"pay invoice res: {payment}")
            checking_id = invoice_data.payment_hash

            fees = req.fees_sat * 1000 if req.fees_sat and req.fees_sat > 0 else 0

            if payment.status != PaymentState.COMPLETE:
                return await self._wait_for_outgoing_payment(checking_id, fees, 10)

            if not isinstance(payment.details, PaymentDetails.LIGHTNING):
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
                req = GetPaymentRequest.PAYMENT_HASH(checking_id)
                payment = self.sdk_services.get_payment(req=req)  # type: ignore
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != PaymentType.RECEIVE:
                    logger.warning(f"unexpected payment type: {payment.status}")
                    return PaymentPendingStatus()
                if payment.status == PaymentState.FAILED:
                    return PaymentFailedStatus()
                if payment.status == PaymentState.COMPLETE and isinstance(
                    payment.details, PaymentDetails.LIGHTNING
                ):
                    return PaymentSuccessStatus(
                        paid=True,
                        fee_msat=int(payment.fees_sat * 1000),
                        preimage=payment.details.preimage,
                    )
                return PaymentPendingStatus()
            except Exception as exc:
                logger.warning(exc)
                return PaymentPendingStatus()

        async def get_payment_status(self, checking_id: str) -> PaymentStatus:
            try:
                req = GetPaymentRequest.PAYMENT_HASH(checking_id)
                payment = self.sdk_services.get_payment(req=req)  # type: ignore
                if payment is None:
                    return PaymentPendingStatus()
                if payment.payment_type != PaymentType.SEND:
                    logger.warning(f"unexpected payment type: {payment.status}")
                    return PaymentPendingStatus()
                if payment.status == PaymentState.COMPLETE:
                    if not isinstance(payment.details, PaymentDetails.LIGHTNING):
                        logger.warning("payment details are not of type LIGHTNING")
                        return PaymentPendingStatus()
                    return PaymentSuccessStatus(
                        fee_msat=int(payment.fees_sat * 1000),
                        preimage=payment.details.preimage,
                    )
                if payment.status == PaymentState.FAILED:
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
            logger.debug(f"waiting for outgoing payment {checking_id} to complete")
            try:
                breez_outgoing_queue[checking_id] = Queue()
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
