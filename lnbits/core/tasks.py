import asyncio
from typing import List

import httpx
from loguru import logger

from lnbits.tasks import register_invoice_listener

from . import db
from .crud import get_balance_notify
from .models import Payment

api_invoice_listeners: List[asyncio.Queue] = []


async def register_task_listeners():
    invoice_paid_queue = asyncio.Queue(5)
    register_invoice_listener(invoice_paid_queue)
    asyncio.create_task(wait_for_paid_invoices(invoice_paid_queue))


async def wait_for_paid_invoices(invoice_paid_queue: asyncio.Queue):
    while True:
        payment = await invoice_paid_queue.get()
        logger.debug("received invoice paid event")
        # send information to sse channel
        await dispatch_invoice_listener(payment)

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


async def dispatch_invoice_listener(payment: Payment):
    for send_channel in api_invoice_listeners:
        try:
            send_channel.put_nowait(payment)
        except asyncio.QueueFull:
            logger.debug("removing sse listener", send_channel)
            api_invoice_listeners.remove(send_channel)


async def dispatch_webhook(payment: Payment):
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
