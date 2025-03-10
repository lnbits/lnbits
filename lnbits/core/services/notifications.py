import asyncio
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http import HTTPStatus
from typing import Optional, Tuple

import httpx
from loguru import logger
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from lnbits.core.crud import (
    delete_webpush_subscriptions,
    get_webpush_subscriptions_for_user,
    mark_webhook_sent,
)
from lnbits.core.models import Payment, Wallet
from lnbits.core.models.notifications import (
    NOTIFICATION_TEMPLATES,
    NotificationMessage,
    NotificationType,
)
from lnbits.core.services.nostr import fetch_nip5_details, send_nostr_dm
from lnbits.core.services.websockets import websocket_manager
from lnbits.helpers import check_callback_url, is_valid_email_address
from lnbits.settings import settings
from lnbits.utils.nostr import normalize_private_key

notifications_queue: asyncio.Queue = asyncio.Queue()


def enqueue_notification(message_type: NotificationType, values: dict) -> None:
    if not is_message_type_enabled(message_type):
        return
    try:
        notifications_queue.put_nowait(
            NotificationMessage(message_type=message_type, values=values)
        )
    except Exception as e:
        logger.error(f"Error enqueuing notification: {e}")


async def process_next_notification():
    notification_message: NotificationMessage = await notifications_queue.get()
    message_type, text = _notification_message_to_text(notification_message)
    await send_notification(text, message_type)


async def send_notification(
    message: str,
    message_type: Optional[str] = None,
) -> None:
    try:
        if settings.lnbits_telegram_notifications_enabled:
            await send_telegram_notification(message)
            logger.debug(f"Sent telegram notification: {message_type}")
    except Exception as e:
        logger.error(f"Error sending telegram notification {message_type}: {e}")

    try:
        if settings.lnbits_nostr_notifications_enabled:
            await send_nostr_notification(message)
            logger.debug(f"Sent nostr notification: {message_type}")
    except Exception as e:
        logger.error(f"Error sending nostr notification {message_type}: {e}")
    try:
        if settings.lnbits_email_notifications_enabled:
            await send_email_notification(message)
            logger.debug(f"Sent email notification: {message_type}")
    except Exception as e:
        logger.error(f"Error sending email notification {message_type}: {e}")


async def send_nostr_notification(message: str) -> dict:
    for i in settings.lnbits_nostr_notifications_identifiers:
        try:
            identifier = await fetch_nip5_details(i)
            user_pubkey = identifier[0]
            relays = identifier[1]
            server_private_key = normalize_private_key(
                settings.lnbits_nostr_notifications_private_key
            )
            await send_nostr_dm(
                server_private_key,
                user_pubkey,
                message,
                relays,
            )
        except Exception as e:
            logger.warning(f"Error notifying identifier {i}: {e}")

    return {"status": "ok"}


async def send_telegram_notification(message: str) -> dict:
    return await send_telegram_message(
        settings.lnbits_telegram_notifications_access_token,
        settings.lnbits_telegram_notifications_chat_id,
        message,
    )


async def send_telegram_message(token: str, chat_id: str, message: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "markdown"}
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload)
        response.raise_for_status()
        return response.json()


async def send_email_notification(
    message: str, subject: str = "LNbits Notification"
) -> dict:
    if not settings.lnbits_email_notifications_enabled:
        return {"status": "error", "message": "Email notifications are disabled"}
    try:
        await send_email(
            settings.lnbits_email_notifications_server,
            settings.lnbits_email_notifications_port,
            settings.lnbits_email_notifications_username,
            settings.lnbits_email_notifications_password,
            settings.lnbits_email_notifications_email,
            settings.lnbits_email_notifications_to_emails,
            subject,
            message,
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")
        return {"status": "error", "message": str(e)}


async def send_email(
    server: str,
    port: int,
    username: str,
    password: str,
    from_email: str,
    to_emails: list[str],
    subject: str,
    message: str,
) -> bool:
    if not is_valid_email_address(from_email):
        raise ValueError(f"Invalid from email address: {from_email}")
    if len(to_emails) == 0:
        raise ValueError("No email addresses provided")
    for email in to_emails:
        if not is_valid_email_address(email):
            raise ValueError(f"Invalid email address: {email}")
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    username = username if len(username) > 0 else from_email
    with smtplib.SMTP(server, port) as smtp_server:
        smtp_server.starttls()
        smtp_server.login(username, password)
        smtp_server.sendmail(from_email, to_emails, msg.as_string())
        return True


def is_message_type_enabled(message_type: NotificationType) -> bool:
    if message_type == NotificationType.balance_update:
        return settings.lnbits_notification_credit_debit
    if message_type == NotificationType.settings_update:
        return settings.lnbits_notification_settings_update
    if message_type == NotificationType.watchdog_check:
        return settings.lnbits_notification_watchdog
    if message_type == NotificationType.balance_delta:
        return settings.notification_balance_delta_changed
    if message_type == NotificationType.server_start_stop:
        return settings.lnbits_notification_server_start_stop
    if message_type == NotificationType.server_status:
        return settings.lnbits_notification_server_status_hours > 0
    if message_type == NotificationType.incoming_payment:
        return settings.lnbits_notification_incoming_payment_amount_sats > 0
    if message_type == NotificationType.outgoing_payment:
        return settings.lnbits_notification_outgoing_payment_amount_sats > 0

    return False


def _notification_message_to_text(
    notification_message: NotificationMessage,
) -> Tuple[str, str]:
    message_type = notification_message.message_type.value
    meesage_value = NOTIFICATION_TEMPLATES.get(message_type, message_type)
    try:
        text = meesage_value.format(**notification_message.values)
    except Exception as e:
        logger.warning(f"Error formatting notification message: {e}")
        text = meesage_value
    text = f"""[{settings.lnbits_site_title}]\n{text}"""
    return message_type, text


async def dispatch_webhook(payment: Payment):
    """
    Dispatches the webhook to the webhook url.
    """
    logger.debug("sending webhook", payment.webhook)

    if not payment.webhook:
        return await mark_webhook_sent(payment.payment_hash, -1)

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers) as client:
        data = payment.dict()
        try:
            check_callback_url(payment.webhook)
            r = await client.post(payment.webhook, json=data, timeout=40)
            r.raise_for_status()
            await mark_webhook_sent(payment.payment_hash, r.status_code)
        except httpx.HTTPStatusError as exc:
            await mark_webhook_sent(payment.payment_hash, exc.response.status_code)
            logger.warning(
                f"webhook returned a bad status_code: {exc.response.status_code} "
                f"while requesting {exc.request.url!r}."
            )
        except httpx.RequestError:
            await mark_webhook_sent(payment.payment_hash, -1)
            logger.warning(f"Could not send webhook to {payment.webhook}")


async def send_payment_notification(wallet: Wallet, payment: Payment):
    try:
        await send_ws_payment_notification(wallet, payment)
    except Exception as e:
        logger.error("Error sending websocket payment notification", e)
    try:
        send_chat_payment_notification(wallet, payment)
    except Exception as e:
        logger.error("Error sending chat payment notification", e)
    try:
        await send_payment_push_notification(wallet, payment)
    except Exception as e:
        logger.error("Error sending push payment notification", e)

    if payment.webhook and not payment.webhook_status:
        await dispatch_webhook(payment)


async def send_ws_payment_notification(wallet: Wallet, payment: Payment):
    # TODO: websocket message should be a clean payment model
    # await websocket_manager.send_data(payment.json(), wallet.inkey)
    # TODO: figure out why we send the balance with the payment here.
    # cleaner would be to have a separate message for the balance
    # and send it with the id of the wallet so wallets can subscribe to it
    payment_notification = json.dumps(
        {
            "wallet_balance": wallet.balance,
            # use pydantic json serialization to get the correct datetime format
            "payment": json.loads(payment.json()),
        },
    )
    await websocket_manager.send_data(payment_notification, wallet.inkey)
    await websocket_manager.send_data(payment_notification, wallet.adminkey)

    await websocket_manager.send_data(
        json.dumps({"pending": payment.pending, "status": payment.status}),
        payment.payment_hash,
    )


def send_chat_payment_notification(wallet: Wallet, payment: Payment):
    amount_sats = abs(payment.sat)
    values: dict = {
        "wallet_id": wallet.id,
        "wallet_name": wallet.name,
        "amount_sats": amount_sats,
        "fiat_value_fmt": "",
    }
    if payment.extra.get("wallet_fiat_currency", None):
        amount_fiat = payment.extra.get("wallet_fiat_amount", None)
        currency = payment.extra.get("wallet_fiat_currency", None)
        values["fiat_value_fmt"] = f"`{amount_fiat}`*{currency}* / "

    if payment.is_out:
        if amount_sats >= settings.lnbits_notification_outgoing_payment_amount_sats:
            enqueue_notification(NotificationType.outgoing_payment, values)
    else:
        if amount_sats >= settings.lnbits_notification_incoming_payment_amount_sats:
            enqueue_notification(NotificationType.incoming_payment, values)


async def send_payment_push_notification(wallet: Wallet, payment: Payment):
    subscriptions = await get_webpush_subscriptions_for_user(wallet.user)

    amount = int(payment.amount / 1000)

    title = f"LNbits: {wallet.name}"
    body = f"You just received {amount} sat{'s'[:amount^1]}!"

    if payment.memo:
        body += f"\r\n{payment.memo}"

    for subscription in subscriptions:
        # todo: review permissions when user-id-only not allowed
        # todo: replace all this logic with websockets?
        url = f"https://{subscription.host}/wallet?usr={wallet.user}&wal={wallet.id}"
        await send_push_notification(subscription, title, body, url)


async def send_push_notification(subscription, title, body, url=""):
    vapid = Vapid()
    try:
        logger.debug("sending push notification")
        webpush(
            json.loads(subscription.data),
            json.dumps({"title": title, "body": body, "url": url}),
            (
                vapid.from_pem(bytes(settings.lnbits_webpush_privkey, "utf-8"))
                if settings.lnbits_webpush_privkey
                else None
            ),
            {"aud": "", "sub": "mailto:alan@lnbits.com"},
        )
    except WebPushException as e:
        if e.response and e.response.status_code == HTTPStatus.GONE:
            # cleanup unsubscribed or expired push subscriptions
            await delete_webpush_subscriptions(subscription.endpoint)
        else:
            logger.error(
                f"failed sending push notification: "
                f"{e.response.text if e.response else e}"
            )
