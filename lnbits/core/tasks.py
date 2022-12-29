import asyncio
from typing import Dict

import httpx
from loguru import logger

from lnbits.tasks import SseListenersDict, register_invoice_listener

from . import db
from .crud import get_balance_notify
from .models import Payment

api_invoice_listeners: Dict[str, asyncio.Queue] = SseListenersDict(
    "api_invoice_listeners"
)


async def register_task_listeners():
    """
    Registers an invoice listener queue for the core tasks.
    Incoming payaments in this queue will eventually trigger the signals sent to all other extensions
    and fulfill other core tasks such as dispatching webhooks.
    """
    invoice_paid_queue = asyncio.Queue(5)
    # we register invoice_paid_queue to receive all incoming invoices
    register_invoice_listener(invoice_paid_queue, "core/tasks.py")
    # register a worker that will react to invoices
    asyncio.create_task(wait_for_paid_invoices(invoice_paid_queue))


async def wait_for_paid_invoices(invoice_paid_queue: asyncio.Queue):
    """
    This worker dispatches events to all extensions, dispatches webhooks and balance notifys.
    """
    while True:
        payment = await invoice_paid_queue.get()
        logger.trace("received invoice paid event")
        # send information to sse channel
        await dispatch_api_invoice_listeners(payment)

        # dispatch webhook
        if payment.webhook and not payment.webhook_status:
            await dispatch_webhook(payment)

        # dispatch balance_notify
        url = await get_balance_notify(payment.wallet_id)
        if url:
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.post(url, timeout=4)
                    await mark_webhook_sent(payment, r.status_code)
                except (httpx.ConnectError, httpx.RequestError):
                    pass


async def dispatch_api_invoice_listeners(payment: Payment):
    """
    Emits events to invoice listener subscribed from the API.
    """
    for chan_name, send_channel in api_invoice_listeners.items():
        try:
            logger.debug(f"sending invoice paid event to {chan_name}")
            send_channel.put_nowait(payment)
        except asyncio.QueueFull:
            logger.error(f"removing sse listener {send_channel}:{chan_name}")
            api_invoice_listeners.pop(chan_name)


async def dispatch_webhook(payment: Payment):
    """
    Dispatches the webhook to the webhook url.
    """
    async with httpx.AsyncClient() as client:
        data = payment.dict()
        try:
            logger.debug("sending webhook", payment.webhook)
            r = await client.post(payment.webhook, json=data, timeout=40)  # type: ignore
            await mark_webhook_sent(payment, r.status_code)
        except (httpx.ConnectError, httpx.RequestError):
            await mark_webhook_sent(payment, -1)


async def mark_webhook_sent(payment: Payment, status: int) -> None:
    await db.execute(
        """
        UPDATE apipayments SET webhook_status = ?
        WHERE hash = ?
        """,
        (status, payment.payment_hash),
    )
