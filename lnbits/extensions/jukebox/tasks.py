import json
import trio  # type: ignore

from lnbits.core.models import Payment
from lnbits.core.crud import create_payment
from lnbits.core import db as core_db
from lnbits.tasks import register_invoice_listener, internal_invoice_paid
from lnbits.helpers import urlsafe_short_hash

from .crud import get_jukebox, update_jukebox_payment


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(2)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "jukebox" != payment.extra.get("tag"):
        # not a jukebox invoice
        return
    await update_jukebox_payment(payment.payment_hash, paid=True)
