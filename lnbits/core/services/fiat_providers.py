import hashlib
import hmac
import time
from typing import Optional

from loguru import logger

from lnbits.core.crud.payments import get_standalone_payment
from lnbits.core.models.misc import SimpleStatus
from lnbits.walletsfiat import get_fiat_provider


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
