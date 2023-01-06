# views_api.py is for you API endpoints that could be hit by another service

# add your dependencies here

import asyncio
from loguru import logger
from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)

async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "example":
        logger.debug(payment)
        # Do something
    return