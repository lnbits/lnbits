import asyncio
import json

from lnbits.core.models import Payment
from lnbits.helpers import urlsafe_short_hash
from lnbits.tasks import internal_invoice_queue, register_invoice_listener

from .crud import (
    create_invoice_payment,
    get_invoice,
    get_invoice_items,
    get_invoice_payments,
    get_invoice_total,
    get_payments_total,
    update_invoice_internal,
)


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "invoices":
        # not relevant
        return

    invoice_id = payment.extra.get("invoice_id")

    payment = await create_invoice_payment(
        invoice_id=invoice_id, amount=payment.extra.get("famount")
    )

    invoice = await get_invoice(invoice_id)

    invoice_items = await get_invoice_items(invoice_id)
    invoice_total = await get_invoice_total(invoice_items)

    invoice_payments = await get_invoice_payments(invoice_id)
    payments_total = await get_payments_total(invoice_payments)

    if payments_total >= invoice_total:
        invoice.status = "paid"
        await update_invoice_internal(invoice.wallet, invoice)

    return
