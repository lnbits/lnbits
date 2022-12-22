import asyncio
import json

import httpx
from loguru import logger

from lnbits.core import db as core_db
from lnbits.core.crud import update_payment_extra
from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_pay_link


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "lnurlp":
        # not an lnurlp invoice
        return

    if payment.extra.get("wh_status"):
        # this webhook has already been sent
        return

    pay_link = await get_pay_link(payment.extra.get("link", -1))
    if pay_link and pay_link.webhook_url:
        async with httpx.AsyncClient() as client:
            try:
                kwargs = {
                    "json": {
                        "payment_hash": payment.payment_hash,
                        "payment_request": payment.bolt11,
                        "amount": payment.amount,
                        "comment": payment.extra.get("comment"),
                        "lnurlp": pay_link.id,
                    },
                    "timeout": 40,
                }
                if pay_link.webhook_body:
                    kwargs["json"]["body"] = json.loads(pay_link.webhook_body)
                if pay_link.webhook_headers:
                    kwargs["headers"] = json.loads(pay_link.webhook_headers)

                r: httpx.Response = await client.post(pay_link.webhook_url, **kwargs)
                await mark_webhook_sent(
                    payment, r.status_code, r.is_success, r.reason_phrase, r.text
                )
            except Exception as ex:
                logger.error(ex)
                await mark_webhook_sent(payment, -1, False, "Unexpected Error", str(ex))


async def mark_webhook_sent(
    payment: Payment, status: int, is_success: bool, reason_phrase="", text=""
) -> None:
    payment.extra["wh_status"] = status  # keep for backwards compability
    payment.extra["wh_success"] = is_success
    payment.extra["wh_message"] = reason_phrase
    payment.extra["wh_response"] = text

    await update_payment_extra(payment.payment_hash, payment.extra)
