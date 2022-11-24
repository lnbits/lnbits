import asyncio
import json
from http import HTTPStatus
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from loguru import logger

from lnbits import bolt11
from lnbits.core.models import Payment
from lnbits.core.services import pay_invoice
from lnbits.extensions.events.models import CreateTicket
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .views_api import api_ticket_send_ticket


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    # (avoid loops)
    if (
        "events" == payment.extra.get("tag")
        and payment.extra.get("name")
        and payment.extra.get("email")
    ):
        CreateTicket.name = str(payment.extra.get("name"))
        CreateTicket.email = str(payment.extra.get("email"))
        await api_ticket_send_ticket(payment.memo, payment.payment_hash, CreateTicket)
    return
