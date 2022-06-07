import asyncio
import json
import httpx

from lnbits.core import db as core_db
from .models import ScrubLink
from lnbits.tasks import register_invoice_listener

from .crud import get_scrub_link


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: ScrubLink) -> None:
    if "scrub" != payment.extra.get("tag"):
        # not an scrub invoice
        return

    if payment.extra.get("wh_status"):
        # this webhook has already been sent
        return

    pay_link = await get_pay_link(payment.extra.get("link", -1))
    # PAY LNURLP AND LNADDRESS


async def mark_webhook_sent(payment: ScrubLink, status: int) -> None:
    payment.extra["wh_status"] = status

    await core_db.execute(
        """
        UPDATE apipayments SET extra = ?
        WHERE hash = ?
        """,
        (json.dumps(payment.extra), payment.payment_hash),
    )
