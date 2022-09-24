import asyncio
import json
from http import HTTPStatus

import httpx
from starlette.exceptions import HTTPException

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_copilot
from .views import updater


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    webhook = None
    data = None
    if payment.extra.get("tag") != "copilot":
        # not an copilot invoice
        return

    copilot = await get_copilot(payment.extra.get("copilotid", -1))

    if not copilot:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Copilot does not exist"
        )
    if copilot.animation1threshold:
        if int(payment.amount / 1000) >= copilot.animation1threshold:
            data = copilot.animation1
            webhook = copilot.animation1webhook
        if copilot.animation2threshold:
            if int(payment.amount / 1000) >= copilot.animation2threshold:
                data = copilot.animation2
                webhook = copilot.animation1webhook
            if copilot.animation3threshold:
                if int(payment.amount / 1000) >= copilot.animation3threshold:
                    data = copilot.animation3
                    webhook = copilot.animation1webhook
    if webhook:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    webhook,
                    json={
                        "payment_hash": payment.payment_hash,
                        "payment_request": payment.bolt11,
                        "amount": payment.amount,
                        "comment": payment.extra.get("comment"),
                    },
                    timeout=40,
                )
                await mark_webhook_sent(payment, r.status_code)
            except (httpx.ConnectError, httpx.RequestError):
                await mark_webhook_sent(payment, -1)
    if payment.extra.get("comment"):
        await updater(copilot.id, data, payment.extra.get("comment"))

    await updater(copilot.id, data, "none")


async def mark_webhook_sent(payment: Payment, status: int) -> None:
    payment.extra["wh_status"] = status

    await core_db.execute(
        """
        UPDATE apipayments SET extra = ?
        WHERE hash = ?
        """,
        (json.dumps(payment.extra), payment.payment_hash),
    )
