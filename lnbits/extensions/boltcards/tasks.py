import asyncio
import json

import httpx
from loguru import logger

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import create_refund, get_card, get_hit


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
    hit = await get_hit(payment.extra.get("refund"))

    if hit:
        refund = await create_refund(
            hit_id=hit.id, refund_amount=(payment.amount / 1000)
        )
        await mark_webhook_sent(payment, 1)

        card = await get_card(hit.card_id)
        if card.webhook_url:
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.post(
                        card.webhook_url,
                        json={
                            "notification": "card_refund",
                            "payment_hash": payment.payment_hash,
                            "payment_request": payment.bolt11,
                            "card_external_id": card.external_id,
                            "card_name": card.card_name,
                            "amount": int(payment.amount / 1000),
                        },
                        timeout=40,
                    )
                except Exception as exc:
                    logger.error("Caught exception when dispatching webhook url:", exc)


async def mark_webhook_sent(payment: Payment, status: int) -> None:
    payment.extra["wh_status"] = status

    await core_db.execute(
        """
        UPDATE apipayments SET extra = ?
        WHERE hash = ?
        """,
        (json.dumps(payment.extra), payment.payment_hash),
    )
