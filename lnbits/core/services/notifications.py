import asyncio
import json
import smtplib
from asyncio.tasks import create_task
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http import HTTPStatus

import httpx
from loguru import logger
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from lnbits.core.crud import (
    delete_webpush_subscriptions,
    get_webpush_subscriptions_for_user,
    mark_webhook_sent,
)
from lnbits.core.crud.users import get_user
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models import Payment, Wallet
from lnbits.core.models.notifications import (
    NOTIFICATION_TEMPLATES,
    NotificationMessage,
    NotificationType,
)
from lnbits.core.models.users import UserNotifications
from lnbits.core.services.nostr import fetch_nip5_details, send_nostr_dm
from lnbits.core.services.websockets import websocket_manager
from lnbits.helpers import check_callback_url, is_valid_email_address
from lnbits.settings import settings
from lnbits.utils.nostr import normalize_private_key

notifications_queue: asyncio.Queue[NotificationMessage] = asyncio.Queue()


def enqueue_admin_notification(message_type: NotificationType, values: dict) -> None:
    if not _is_message_type_enabled(message_type):
        return
    try:
        notifications_queue.put_nowait(
            NotificationMessage(message_type=message_type, values=values)
        )
    except Exception as e:
        logger.error(f"Error enqueuing notification: {e}")


def enqueue_user_notification(
    message_type: NotificationType, values: dict, user_notifications: UserNotifications
) -> None:
    try:
        notifications_queue.put_nowait(
            NotificationMessage(
                message_type=message_type,
                values=values,
                user_notifications=user_notifications,
            )
        )
    except Exception as e:
        logger.error(f"Error enqueuing notification: {e}")


async def process_next_notification() -> None:
    notification_message = await notifications_queue.get()
    message_type, text = _notification_message_to_text(notification_message)
    user_notifications = notification_message.user_notifications
    if user_notifications:
        await send_user_notification(user_notifications, text, message_type)
    else:
        await send_admin_notification(text, message_type)


async def send_admin_notification(
    message: str,
    message_type: str | None = None,
) -> None:
    return await send_notification(
        settings.lnbits_telegram_notifications_chat_id,
        settings.lnbits_nostr_notifications_identifiers,
        settings.lnbits_email_notifications_to_emails,
        message,
        message_type,
    )


async def send_user_notification(
    user_notifications: UserNotifications,
    message: str,
    message_type: str | None = None,
) -> None:

    email_address = (
        [user_notifications.email_address] if user_notifications.email_address else []
    )
    nostr_identifiers = (
        [user_notifications.nostr_identifier]
        if user_notifications.nostr_identifier
        else []
    )
    return await send_notification(
        user_notifications.telegram_chat_id,
        nostr_identifiers,
        email_address,
        message,
        message_type,
    )


async def send_notification(
    telegram_chat_id: str | None,
    nostr_identifiers: list[str] | None,
    email_addresses: list[str] | None,
    message: str,
    message_type: str | None = None,
) -> None:
    try:
        if telegram_chat_id and settings.is_telegram_notifications_configured():
            await send_telegram_notification(telegram_chat_id, message)
            logger.debug(f"Sent telegram notification: {message_type}")
    except Exception as e:
        logger.error(f"Error sending telegram notification {message_type}: {e}")

    try:
        if nostr_identifiers and settings.is_nostr_notifications_configured():
            await send_nostr_notifications(nostr_identifiers, message)
            logger.debug(f"Sent nostr notification: {message_type}")
    except Exception as e:
        logger.error(f"Error sending nostr notification {message_type}: {e}")
    try:
        if email_addresses and settings.lnbits_email_notifications_enabled:
            await send_email_notification(email_addresses, message)
            logger.debug(f"Sent email notification: {message_type}")
    except Exception as e:
        logger.error(f"Error sending email notification {message_type}: {e}")


async def send_nostr_notifications(identifiers: list[str], message: str) -> list[str]:
    success_sent: list[str] = []
    for identifier in identifiers:
        try:
            await send_nostr_notification(identifier, message)
            success_sent.append(identifier)
        except Exception as e:
            logger.warning(f"Error notifying identifier {identifier}: {e}")
    return success_sent


async def send_nostr_notification(identifier: str, message: str):
    nip5 = await fetch_nip5_details(identifier)
    user_pubkey = nip5[0]
    relays = nip5[1]
    server_private_key = normalize_private_key(
        settings.lnbits_nostr_notifications_private_key
    )
    await send_nostr_dm(
        server_private_key,
        user_pubkey,
        message,
        relays,
    )


async def send_telegram_notification(chat_id: str, message: str) -> dict:
    return await send_telegram_message(
        settings.lnbits_telegram_notifications_access_token,
        chat_id,
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
    to_emails: list[str], message: str, subject: str = "LNbits Notification"
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
            to_emails,
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


async def dispatch_webhook(payment: Payment):
    """
    Dispatches the webhook to the webhook url.
    """
    logger.debug("sending webhook", payment.webhook)

    if not payment.webhook:
        return await mark_webhook_sent(payment.payment_hash, "-1")

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            check_callback_url(payment.webhook)
        except ValueError as exc:
            await mark_webhook_sent(payment.payment_hash, "-1")
            logger.warning(f"Invalid webhook URL {payment.webhook}: {exc!s}")
        try:
            r = await client.post(payment.webhook, json=payment.json(), timeout=40)
            r.raise_for_status()
            await mark_webhook_sent(payment.payment_hash, str(r.status_code))
        except httpx.HTTPStatusError as exc:
            await mark_webhook_sent(payment.payment_hash, str(exc.response.status_code))
            logger.warning(
                f"webhook returned a bad status_code: {exc.response.status_code} "
                f"while requesting {exc.request.url!r}."
            )
        except httpx.RequestError:
            await mark_webhook_sent(payment.payment_hash, "-1")
            logger.warning(f"Could not send webhook to {payment.webhook}")


async def send_payment_notification(wallet: Wallet, payment: Payment):
    try:
        await send_ws_payment_notification(wallet, payment)
        for shared in wallet.extra.shared_with:
            if not shared.shared_with_wallet_id:
                continue
            shared_wallet = await get_wallet(shared.shared_with_wallet_id)
            if shared_wallet and shared_wallet.can_view_payments:
                await send_ws_payment_notification(shared_wallet, payment)
    except Exception as e:
        logger.error(f"Error sending websocket payment notification {e!s}")
    try:
        await send_chat_payment_notification(wallet, payment)
    except Exception as e:
        logger.error(f"Error sending chat payment notification {e!s}")
    try:
        await send_payment_push_notification(wallet, payment)
    except Exception as e:
        logger.error(f"Error sending push payment notification {e!s}")

    try:
        if payment.webhook and not payment.webhook_status:
            await dispatch_webhook(payment)
    except Exception as e:
        logger.error(f"Error dispatching webhook: {e!s}")


def send_payment_notification_in_background(wallet: Wallet, payment: Payment):
    try:
        create_task(send_payment_notification(wallet, payment))
    except Exception as e:
        logger.warning(f"Error sending payment notification: {e}")


async def send_ws_payment_notification(wallet: Wallet, payment: Payment):
    # TODO: websocket message should be a clean payment model
    # await websocket_manager.send(wallet.inkey, payment.json())
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
    await websocket_manager.send(wallet.inkey, payment_notification)
    await websocket_manager.send(wallet.adminkey, payment_notification)
    await websocket_manager.send(
        payment.payment_hash,
        json.dumps({"pending": payment.pending, "status": payment.status}),
    )


async def send_chat_payment_notification(wallet: Wallet, payment: Payment):
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
            enqueue_admin_notification(NotificationType.outgoing_payment, values)
    elif amount_sats >= settings.lnbits_notification_incoming_payment_amount_sats:
        enqueue_admin_notification(NotificationType.incoming_payment, values)

    user = await get_user(wallet.user)
    user_notifications = user.extra.notifications if user else None
    if user_notifications and wallet.id not in user_notifications.excluded_wallets:
        out_limit = user_notifications.outgoing_payments_sats
        in_limit = user_notifications.incoming_payments_sats
        if payment.is_out and (amount_sats >= out_limit):
            enqueue_user_notification(
                NotificationType.outgoing_payment, values, user_notifications
            )
        elif amount_sats >= in_limit:
            enqueue_user_notification(
                NotificationType.incoming_payment, values, user_notifications
            )


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


def _is_message_type_enabled(message_type: NotificationType) -> bool:
    if message_type == NotificationType.balance_update:
        return settings.lnbits_notification_credit_debit
    if message_type == NotificationType.settings_update:
        return settings.lnbits_notification_settings_update
    if message_type == NotificationType.watchdog_check:
        return settings.lnbits_notification_watchdog
    if message_type == NotificationType.balance_delta:
        return settings.notification_balance_delta_threshold_sats > 0
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
) -> tuple[str, str]:
    message_type = notification_message.message_type.value
    meesage_value = NOTIFICATION_TEMPLATES.get(message_type, message_type)
    try:
        text = meesage_value.format(**notification_message.values)
    except Exception as e:
        logger.warning(f"Error formatting notification message: {e}")
        text = meesage_value
    text = f"""[{settings.lnbits_site_title}]\n{text}"""
    return message_type, text
