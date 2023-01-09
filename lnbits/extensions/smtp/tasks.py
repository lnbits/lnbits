import asyncio
from http import HTTPStatus

import httpx
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import (
    delete_email,
    get_email,
    get_emailaddress,
    get_emailaddress_by_email,
    set_email_paid,
)
from .smtp import send_mail


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or "smtp" != payment.extra.get("tag"):
        # not an lnurlp invoice
        return

    email = await get_email(payment.checking_id)
    if not email:
        logger.error("SMTP: email can not by fetched")
        return

    emailaddress = await get_emailaddress(email.emailaddress_id)
    if not emailaddress:
        logger.error("SMTP: emailaddress can not by fetched")
        return

    await payment.set_pending(False)
    await send_mail(emailaddress, email)
    await set_email_paid(payment_hash=payment.payment_hash)
