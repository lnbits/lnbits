import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import get_ticket, set_ticket_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
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
    print("ticket", _ticket)
