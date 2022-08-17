import asyncio
import json

import httpx

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import get_Podcast

async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        Payment = await invoice_queue.get()
        await on_invoice_paid(Payment)


async def on_invoice_paid(Payment: Payment) -> None:
    if Payment.extra.get("tag") != "Payment":
        # not an Payment invoice
        return

    if Payment.extra.get("wh_status"):
        # this webhook has already been sent
        return

    Payment = await get_payment(Payment.extra.get("pod", -1))
    if Payment and Payment.webhook_url:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    Payment.webhook_url,
                    json={
                        "Payment_hash": Payment.Payment_hash,
                        "Payment_request": Payment.bolt11,
                        "amount": Payment.amount,
                        "comment": Payment.extra.get("comment"),
                        "Payment": Payment.id,
                    },
                    timeout=40,
                )
                await mark_webhook_sent(Payment, r.status_code)
            except (httpx.ConnectError, httpx.RequestError):
                await mark_webhook_sent(Payment, -1)


async def mark_webhook_sent(Payment: Payment, status: int) -> None:
    Payment.extra["wh_status"] = status

    await core_db.execute(
        """
        UPDATE apiPayments SET extra = ?
        WHERE hash = ?
        """,
        (json.dumps(Payment.extra), Payment.Payment_hash),
    )
