import asyncio
import json

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import create_refund, get_hit


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:

    if not payment.extra.get("refund"):
        return

    if payment.extra.get("wh_status"):
        # this webhook has already been sent
        return

    hit = await get_hit(str(payment.extra.get("refund")))

    if hit:
        await create_refund(hit_id=hit.id, refund_amount=(payment.amount / 1000))
        await mark_webhook_sent(payment, 1)


async def mark_webhook_sent(payment: Payment, status: int) -> None:

    payment.extra["wh_status"] = status

    await core_db.execute(
        """
        UPDATE apipayments SET extra = ?
        WHERE hash = ?
        """,
        (json.dumps(payment.extra), payment.payment_hash),
    )
