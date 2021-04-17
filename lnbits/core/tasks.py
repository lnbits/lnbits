import trio  # type: ignore
import httpx
from typing import List

from lnbits.tasks import register_invoice_listener

from . import db
from .crud import get_balance_notify
from .models import Payment

sse_listeners: List[trio.MemorySendChannel] = []


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(5)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        # send information to sse channel
        await dispatch_sse(payment)

        # dispatch webhook
        if payment.webhook and not payment.webhook_status:
            await dispatch_webhook(payment)

        # dispatch balance_notify
        url = await get_balance_notify(payment.wallet_id)
        if url:
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.post(
                        url,
                        timeout=4,
                    )
                    await mark_webhook_sent(payment, r.status_code)
                except (httpx.ConnectError, httpx.RequestError):
                    pass


async def dispatch_sse(payment: Payment):
    for send_channel in sse_listeners:
        try:
            send_channel.send_nowait(payment)
        except trio.WouldBlock:
            print("removing sse listener", send_channel)
            sse_listeners.remove(send_channel)


async def dispatch_webhook(payment: Payment):
    async with httpx.AsyncClient() as client:
        data = payment._asdict()
        try:
            r = await client.post(
                payment.webhook,
                json=data,
                timeout=40,
            )
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
