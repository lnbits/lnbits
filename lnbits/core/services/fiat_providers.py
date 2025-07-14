import hashlib
import hmac
import time
from typing import Optional

from loguru import logger

from lnbits.core.crud import get_wallet
from lnbits.core.crud.payments import create_payment, get_standalone_payment
from lnbits.core.models import CreatePayment, Payment, PaymentState
from lnbits.core.models.misc import SimpleStatus
from lnbits.db import Connection
from lnbits.fiat import get_fiat_provider
from lnbits.settings import settings


async def handle_fiat_payment_confirmation(
    payment: Payment, conn: Optional[Connection] = None
):
    try:
        await _credit_fiat_service_fee_wallet(payment, conn=conn)
    except Exception as e:
        logger.warning(e)

    try:
        await _debit_fiat_service_faucet_wallet(payment, conn=conn)
    except Exception as e:
        logger.warning(e)


async def _credit_fiat_service_fee_wallet(
    payment: Payment, conn: Optional[Connection] = None
):
    fiat_provider_name = payment.fiat_provider
    if not fiat_provider_name:
        return
    if payment.fee == 0:
        return

    limits = settings.get_fiat_provider_limits(fiat_provider_name)
    if not limits:
        return

    if not limits.service_fee_wallet_id:
        return

    memo = (
        f"Service fee for fiat payment of "
        f"{abs(payment.sat)} sats. "
        f"Provider: {fiat_provider_name}. "
        f"Wallet: '{payment.wallet_id}'."
    )
    create_payment_model = CreatePayment(
        wallet_id=limits.service_fee_wallet_id,
        bolt11=payment.bolt11,
        payment_hash=payment.payment_hash,
        amount_msat=abs(payment.fee),
        memo=memo,
    )
    await create_payment(
        checking_id=f"service_fee_{payment.payment_hash}",
        data=create_payment_model,
        status=PaymentState.SUCCESS,
        conn=conn,
    )


async def _debit_fiat_service_faucet_wallet(
    payment: Payment, conn: Optional[Connection] = None
):
    fiat_provider_name = payment.fiat_provider
    if not fiat_provider_name:
        return

    limits = settings.get_fiat_provider_limits(fiat_provider_name)
    if not limits:
        return

    if not limits.service_faucet_wallet_id:
        return

    faucet_wallet = await get_wallet(limits.service_faucet_wallet_id, conn=conn)
    if not faucet_wallet:
        raise ValueError(
            f"Fiat provider '{fiat_provider_name}' faucet wallet not found."
        )

    memo = (
        f"Faucet payment of {abs(payment.sat)} sats. "
        f"Provider: {fiat_provider_name}. "
        f"Wallet: '{payment.wallet_id}'."
    )
    create_payment_model = CreatePayment(
        wallet_id=limits.service_faucet_wallet_id,
        bolt11=payment.bolt11,
        payment_hash=payment.payment_hash,
        amount_msat=-abs(payment.amount),
        memo=memo,
        extra=payment.extra,
    )
    await create_payment(
        checking_id=f"internal_fiat_{fiat_provider_name}_"
        f"faucet_{payment.payment_hash}",
        data=create_payment_model,
        status=PaymentState.SUCCESS,
        conn=conn,
    )


async def handle_stripe_event(event: dict):
    event_id = event.get("id")
    event_object = event.get("data", {}).get("object", {})
    object_type = event_object.get("object")
    payment_hash = event_object.get("metadata", {}).get("payment_hash")
    logger.debug(
        f"Handling Stripe event: '{event_id}'. Type: '{object_type}'."
        f" Payment hash: '{payment_hash}'."
    )
    if not payment_hash:
        logger.warning("Stripe event does not contain a payment hash.")
        return

    payment = await get_standalone_payment(payment_hash)
    if not payment:
        logger.warning(f"No payment found for hash: '{payment_hash}'.")
        return
    await payment.check_fiat_status()


def check_stripe_signature(
    payload: bytes,
    sig_header: Optional[str],
    secret: Optional[str],
    tolerance_seconds=300,
):
    if not sig_header:
        logger.warning("Stripe-Signature header is missing.")
        raise ValueError("Stripe-Signature header is missing.")

    if not secret:
        logger.warning("Stripe webhook signing secret is not set.")
        raise ValueError("Stripe webhook cannot be verified.")

    # Split the Stripe-Signature header
    items = dict(i.split("=") for i in sig_header.split(","))
    timestamp = int(items["t"])
    signature = items["v1"]

    # Check timestamp tolerance
    if abs(time.time() - timestamp) > tolerance_seconds:
        logger.warning("Timestamp outside tolerance.")
        logger.debug(
            f"Current time: {time.time()}, "
            f"Timestamp: {timestamp}, "
            f"Tolerance: {tolerance_seconds} seconds"
        )

        raise ValueError("Timestamp outside tolerance." f"Timestamp: {timestamp}")

    signed_payload = f"{timestamp}.{payload.decode()}"

    # Compute HMAC SHA256 using the webhook secret
    computed_signature = hmac.new(
        key=secret.encode(), msg=signed_payload.encode(), digestmod=hashlib.sha256
    ).hexdigest()

    # Compare signatures using constant time comparison
    if hmac.compare_digest(computed_signature, signature) is not True:
        logger.warning("Stripe signature verification failed.")
        raise ValueError("Stripe signature verification failed.")


async def test_connection(provider: str) -> SimpleStatus:
    """
    Test the connection to Stripe by checking if the API key is valid.
    This function should be called when setting up or testing the Stripe integration.
    """
    fiat_provider = await get_fiat_provider(provider)
    status = await fiat_provider.status()
    if status.error_message:
        return SimpleStatus(
            success=False,
            message=f"Cconnection test failed: {status.error_message}",
        )

    return SimpleStatus(
        success=True,
        message="Connection test successful." f" Balance: {status.balance}.",
    )
