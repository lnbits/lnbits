import hashlib
import hmac
import json
import time
from base64 import b64encode

import httpx
from loguru import logger

from lnbits.core.crud import get_wallet
from lnbits.core.crud.payments import (
    get_standalone_payment,
    settle_fiat_payment,
    update_payment,
)
from lnbits.core.models import Payment, PaymentState
from lnbits.core.models.misc import SimpleStatus
from lnbits.db import Connection
from lnbits.fiat import get_fiat_provider
from lnbits.fiat.base import (
    FiatPaymentFailedStatus,
    FiatPaymentPendingStatus,
    FiatPaymentStatus,
    FiatPaymentSuccessStatus,
)
from lnbits.settings import settings
from lnbits.task_manager import task_manager


async def handle_fiat_payment_confirmation(
    payment: Payment, conn: Connection | None = None
):
    """Confirm a verified receipt once, without Lightning fees or faucet transfers."""
    settled = await settle_fiat_payment(payment, conn=conn)
    current = settled or await get_standalone_payment(
        payment.checking_id, wallet_id=payment.wallet_id, conn=conn
    )
    if current:
        payment.status = current.status
        payment.fee = current.fee
    if settled:
        task_manager.internal_invoice_queue.put_nowait(settled)


async def check_fiat_status(  # noqa: C901
    payment: Payment, conn: Connection | None = None
) -> FiatPaymentStatus:
    if not payment.is_internal:
        return FiatPaymentPendingStatus()
    current = await get_standalone_payment(
        payment.checking_id, wallet_id=payment.wallet_id, conn=conn
    )
    if not current:
        return FiatPaymentFailedStatus()
    payment.status = current.status
    if payment.fiat_provider:
        wallet = await get_wallet(payment.wallet_id, conn=conn)
        if not wallet or not wallet.is_fiat_wallet:
            raise ValueError("Fiat payments can only be credited to fiat wallets.")
    terminal_status = {
        PaymentState.SUCCESS.value: FiatPaymentSuccessStatus,
        PaymentState.FAILED.value: FiatPaymentFailedStatus,
        PaymentState.DELETED.value: FiatPaymentFailedStatus,
    }.get(current.status)
    if terminal_status:
        return terminal_status()
    checking_id = current.extra.get("fiat_checking_id")
    if not current.fiat_provider or not checking_id:
        return FiatPaymentPendingStatus()
    fiat_provider = await get_fiat_provider(current.fiat_provider)
    if not fiat_provider:
        return FiatPaymentPendingStatus()
    fiat_status = await fiat_provider.get_invoice_status(checking_id)
    if fiat_status.success:
        await handle_fiat_payment_confirmation(payment, conn=conn)
        if not payment.success:
            return FiatPaymentFailedStatus()
    elif fiat_status.failed:
        return await _record_fiat_failure(payment, current, conn)
    return fiat_status


async def _record_fiat_failure(
    payment: Payment, current: Payment, conn: Connection | None
) -> FiatPaymentStatus:
    current.status = PaymentState.FAILED
    await update_payment(current, conn=conn)
    # A concurrent successful confirmation or deletion takes precedence.
    stored = await get_standalone_payment(
        payment.checking_id, wallet_id=payment.wallet_id, conn=conn
    )
    if stored:
        payment.status = stored.status
        if stored.success:
            return FiatPaymentSuccessStatus()
    return FiatPaymentFailedStatus()


def check_stripe_signature(
    payload: bytes,
    sig_header: str | None,
    secret: str | None,
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


async def verify_paypal_webhook(headers, payload: bytes):
    """
    Validate PayPal webhook signatures using the PayPal verify API.
    """
    webhook_id = settings.paypal_webhook_id
    if not webhook_id:
        logger.warning("PayPal webhook ID not set.")
        raise ValueError("PayPal webhook cannot be verified. Missing webhook ID.")

    required_headers = {
        "PAYPAL-TRANSMISSION-ID": headers.get("PAYPAL-TRANSMISSION-ID"),
        "PAYPAL-TRANSMISSION-TIME": headers.get("PAYPAL-TRANSMISSION-TIME"),
        "PAYPAL-TRANSMISSION-SIG": headers.get("PAYPAL-TRANSMISSION-SIG"),
        "PAYPAL-CERT-URL": headers.get("PAYPAL-CERT-URL"),
        "PAYPAL-AUTH-ALGO": headers.get("PAYPAL-AUTH-ALGO"),
    }
    if not all(required_headers.values()):
        logger.warning("Missing PayPal webhook headers.")
        raise ValueError("PayPal webhook cannot be verified. Missing headers.")

    try:
        async with httpx.AsyncClient(base_url=settings.paypal_api_endpoint) as client:
            token_resp = await client.post(
                "/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(
                    settings.paypal_client_id or "",
                    settings.paypal_client_secret or "",
                ),
            )
            token_resp.raise_for_status()
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise ValueError("PayPal token missing in verification flow.")

            verify_resp = await client.post(
                "/v1/notifications/verify-webhook-signature",
                json={
                    "auth_algo": required_headers["PAYPAL-AUTH-ALGO"],
                    "cert_url": required_headers["PAYPAL-CERT-URL"],
                    "transmission_id": required_headers["PAYPAL-TRANSMISSION-ID"],
                    "transmission_sig": required_headers["PAYPAL-TRANSMISSION-SIG"],
                    "transmission_time": required_headers["PAYPAL-TRANSMISSION-TIME"],
                    "webhook_id": webhook_id,
                    "webhook_event": json.loads(payload.decode()),
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            verify_resp.raise_for_status()
            verification_status = verify_resp.json().get("verification_status")
            if verification_status != "SUCCESS":
                raise ValueError("PayPal webhook verification failed.")
    except Exception as exc:
        logger.warning(exc)
        raise ValueError("PayPal webhook cannot be verified.") from exc


def check_square_signature(
    payload: bytes,
    sig_header: str | None,
    secret: str | None,
    notification_url: str | None,
):
    if not sig_header:
        logger.warning("Square signature header is missing.")
        raise ValueError("Square signature header is missing.")

    if not secret:
        logger.warning("Square webhook signature key is not set.")
        raise ValueError("Square webhook cannot be verified.")

    if not notification_url:
        logger.warning("Square webhook notification URL is not set.")
        raise ValueError("Square webhook cannot be verified.")

    signed_payload = notification_url.encode() + payload
    computed_signature = b64encode(
        hmac.new(
            key=secret.encode(), msg=signed_payload, digestmod=hashlib.sha256
        ).digest()
    ).decode()

    if hmac.compare_digest(computed_signature, sig_header) is not True:
        logger.warning("Square signature verification failed.")
        raise ValueError("Square signature verification failed.")


def check_revolut_signature(
    payload: bytes,
    sig_header: str | None,
    timestamp_header: str | None,
    secret: str | None,
    tolerance_seconds=300,
):
    if not sig_header:
        logger.warning("Revolut signature header is missing.")
        raise ValueError("Revolut signature header is missing.")

    if not timestamp_header:
        logger.warning("Revolut timestamp header is missing.")
        raise ValueError("Revolut timestamp header is missing.")

    if not secret:
        logger.warning("Revolut webhook signing secret is not set.")
        raise ValueError("Revolut webhook cannot be verified.")

    try:
        timestamp = int(timestamp_header)
    except ValueError as exc:
        logger.warning("Invalid Revolut timestamp.")
        raise ValueError("Invalid Revolut timestamp.") from exc

    timestamp_seconds = timestamp / 1000 if timestamp > 9999999999 else timestamp

    if abs(time.time() - timestamp_seconds) > tolerance_seconds:
        logger.warning("Timestamp outside tolerance.")
        raise ValueError("Timestamp outside tolerance." f"Timestamp: {timestamp}")

    signed_payload = b"v1." + timestamp_header.encode() + b"." + payload
    digest = hmac.new(
        key=secret.encode(), msg=signed_payload, digestmod=hashlib.sha256
    ).hexdigest()
    expected_signature = f"v1={digest}"

    provided_signatures = [sig.strip() for sig in sig_header.split(",") if sig.strip()]
    if not any(
        hmac.compare_digest(expected_signature, provided)
        for provided in provided_signatures
    ):
        logger.warning("Revolut signature verification failed.")
        raise ValueError("Revolut signature verification failed.")


async def test_connection(provider: str) -> SimpleStatus:
    """
    Test the connection to Stripe by checking if the API key is valid.
    This function should be called when setting up or testing the Stripe integration.
    """
    fiat_provider = await get_fiat_provider(provider)
    if not fiat_provider:
        return SimpleStatus(
            success=False,
            message=f"Fiat provider '{provider}' not found.",
        )
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
