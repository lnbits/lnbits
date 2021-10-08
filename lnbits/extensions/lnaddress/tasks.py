from http import HTTPStatus
from quart.json import jsonify
import trio
import httpx

from .crud import get_domain, set_address_paid, set_address_renewed, get_address
from lnbits.core.crud import get_user, get_wallet
from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(2)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        await on_invoice_paid(payment)


async def call_webhook_on_paid(payment_hash):
    ### Use webhook to notify about cloudflare registration
    address = await get_address(payment_hash)
    domain = await get_domain(address.domain)

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
        except AssertionError:
            webhook = None


async def on_invoice_paid(payment: Payment) -> None:
    if "lnaddress" == payment.extra.get("tag"):

        await payment.set_pending(False)
        await set_address_paid(payment_hash=payment.payment_hash)
        await call_webhook_on_paid(payment.payment_hash)

    elif "renew lnaddress" == payment.extra.get("tag"):

        await payment.set_pending(False)
        await set_address_renewed(address_id=payment.extra["id"], duration=payment.extra["duration"])
        await call_webhook_on_paid(payment.payment_hash)

    else:
        return
