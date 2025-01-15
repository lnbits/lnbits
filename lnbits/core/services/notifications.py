from typing import Optional

import httpx
from loguru import logger

from lnbits.settings import settings


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
