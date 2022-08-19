import asyncio

from loguru import logger

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import get_diagonalley_order_invoiceid, set_diagonalley_order_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "diagonalley":
        return

    order = await get_diagonalley_order_invoiceid(payment.payment_hash)
    if not order:
        logger.error("this should never happen", payment)
        return

    # set order as paid
    await set_diagonalley_order_paid(payment.payment_hash)
    
    # deduct items sold from stock
    # TODO

    
    """
    if "lnticket" != payment.extra.get("tag"):
        # not a lnticket invoice
        return

    ticket = await get_ticket(payment.checking_id)
    if not ticket:
        print("this should never happen", payment)
        return

    await payment.set_pending(False)
    await set_ticket_paid(payment.payment_hash)
    """
