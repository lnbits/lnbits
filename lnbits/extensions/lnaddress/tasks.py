import asyncio

import httpx
from loguru import logger

from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_address, get_domain, set_address_paid, set_address_renewed


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def call_webhook_on_paid(payment_hash):
    ### Use webhook to notify about cloudflare registration
    address = await get_address(payment_hash)
    assert address
    domain = await get_domain(address.domain)
    assert domain

    if not domain.webhook:
        return

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                domain.webhook,
                json={
                    "domain": domain.domain,
                    "address": address.username,
                    "email": address.email,
                    "cost": str(address.sats) + " sats",
                    "duration": str(address.duration) + " days",
                },
                timeout=40,
            )
            r.raise_for_status()
        except Exception as e:
            logger.error(f"lnaddress: error calling webhook on paid: {str(e)}")


async def on_invoice_paid(payment: Payment) -> None:

    if payment.extra.get("tag") == "lnaddress":
        await payment.set_pending(False)
        await set_address_paid(payment_hash=payment.payment_hash)
        await call_webhook_on_paid(payment_hash=payment.payment_hash)

    elif payment.extra.get("tag") == "renew lnaddress":
        await payment.set_pending(False)
        await set_address_renewed(
            address_id=payment.extra["id"], duration=payment.extra["duration"]
        )
        await call_webhook_on_paid(payment_hash=payment.payment_hash)
    else:
        return
