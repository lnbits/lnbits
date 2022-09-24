import asyncio

from loguru import logger

from lnbits.core.models import Payment
from lnbits.extensions.satspay.crud import check_address_balance, get_charge
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

# from .crud import get_ticket, set_ticket_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "charge":
        # not a charge invoice
        return

    charge = await get_charge(payment.memo)
    if not charge:
        logger.error("this should never happen", payment)
        return

    await payment.set_pending(False)
    await check_address_balance(charge_id=charge.id)
