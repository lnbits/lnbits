import asyncio
from typing import Optional, Tuple

import httpx
from loguru import logger

from lnbits.core.models.notifications import (
    NOTIFICATION_TEMPLATES,
    NotificationMessage,
    NotificationType,
)
from lnbits.settings import settings

notifications_queue: asyncio.Queue = asyncio.Queue()


def enqueue_text_notification(text: str):
    enqueue_notification(
        message_type=NotificationType.text_message, values={"message": text}
    )


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


async def send_nostr_notification(message: str) -> dict:
    print("### todo nostr message", message)
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


def is_message_type_enabled(message_type: NotificationType) -> bool:
    if message_type == NotificationType.balance_update:
        return settings.lnbits_notification_credit_debit
    if message_type == NotificationType.settings_update:
        return settings.lnbits_notification_settings_update
    if message_type == NotificationType.balance_delta:
        return settings.lnbits_notification_watchdog
    if message_type == NotificationType.server_start_stop:
        return settings.lnbits_notification_server_start_stop

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
