import trio  # type: ignore
import httpx
from typing import List

from lnbits.tasks import register_invoice_listener

sse_listeners: List[trio.MemorySendChannel] = []


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(5)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        # send information to sse channel
        for send_channel in sse_listeners:
            try:
                send_channel.send_nowait(payment)
            except trio.WouldBlock:
                print("removing sse listener", send_channel)
                sse_listeners.remove(send_channel)

        # dispatch webhook
        if payment.extra and "webhook" in payment.extra:
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(payment.extra["webhook"], json=payment._asdict(), timeout=40)
                except (httpx.ConnectError, httpx.RequestError):
                    pass
