import asyncio
import json

import httpx

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import create_refund, get_hit


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag")[0:6] != "Refund":
        # not an lnurlp invoice
        return

    if payment.extra.get("wh_status"):
        # this webhook has already been sent
        return
    hit = await get_hit(payment.extra.get("tag")[7 : len(payment.extra.get("tag"))])
    if hit:
        refund = await create_refund(
            hit_id=hit.id, refund_amount=payment.extra.get("amount")
        )
        await mark_webhook_sent(payment, 1)
