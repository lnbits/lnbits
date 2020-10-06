import trio  # type: ignore
from typing import List

from .models import Payment

sse_listeners: List[trio.MemorySendChannel] = []


async def on_invoice_paid(payment: Payment):
    for send_channel in sse_listeners:
        try:
            send_channel.send_nowait(payment)
        except trio.WouldBlock:
            print("removing sse listener", send_channel)
            sse_listeners.remove(send_channel)
