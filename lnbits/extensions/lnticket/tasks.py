import json
import trio  # type: ignore

from lnbits.core.models import Payment
from lnbits.core.crud import create_payment
from lnbits.core import db as core_db
from lnbits.tasks import register_invoice_listener, internal_invoice_paid
from lnbits.helpers import urlsafe_short_hash

from .crud import get_ticket, set_ticket_paid


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(2)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        await on_invoice_paid(payment)

async def on_invoice_paid(payment: Payment) -> None:
    if "lnticket" != payment.extra.get("tag"):
        # not a lnticket invoice
        return

    ticket = await get_ticket(payment.checking_id)
    if not ticket:
        print("this should never happen", payment)
        return

    await payment.set_pending(False)
    await set_ticket_paid(payment.payment_hash)
    _ticket = await get_ticket(payment.checking_id)
    print('ticket', _ticket)
