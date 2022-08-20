import asyncio

from loguru import logger

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import get_reverse_submarine_swap, get_submarine_swap, update_swap_status

# from .crud import get_ticket, set_ticket_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "boltz" != payment.extra.get("tag"):
        # not a boltz invoice
        return

    await payment.set_pending(False)
    swap_id = payment.extra.get("swap_id")
    if payment.extra.get("reverse") is not None:
        swap = await get_reverse_submarine_swap(swap_id)
    else:
        swap = await get_submarine_swap(swap_id)

    if not swap:
        logger.error("swap not found. updating status failed.")
        return

    await update_swap_status(swap, "complete")
