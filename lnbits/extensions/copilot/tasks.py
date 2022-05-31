import trio  # type: ignore
import json
import httpx
from quart import g, jsonify, url_for, websocket
from http import HTTPStatus

from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import get_copilot
from .views import updater
import shortuuid


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(2)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    webhook = None
    data = None
    if "copilot" != payment.extra.get("tag"):
        # not an copilot invoice
        return

    if payment.extra.get("wh_status"):
        # this webhook has already been sent
        return

    copilot = await get_copilot(payment.extra.get("copilot", -1))

    if not copilot:
        return (
            jsonify({"message": "Copilot link link does not exist."}),
            HTTPStatus.NOT_FOUND,
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
    else:
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
