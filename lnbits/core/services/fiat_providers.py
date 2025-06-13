from loguru import logger

from lnbits.core.crud.payments import get_standalone_payment
from lnbits.core.models.misc import SimpleStatus
from lnbits.walletsfiat import get_fiat_provider


async def handle_stripe_event(event: dict):
    # todo: check signature
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
