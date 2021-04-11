from http import HTTPStatus
from quart.json import jsonify
import trio  # type: ignore
import httpx

from .crud import get_domain, set_subdomain_paid
from lnbits.core.crud import get_user, get_wallet
from lnbits.core import db as core_db
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from .cloudflare import cloudflare_create_subdomain


async def register_listeners():
    invoice_paid_chan_send, invoice_paid_chan_recv = trio.open_memory_channel(2)
    register_invoice_listener(invoice_paid_chan_send)
    await wait_for_paid_invoices(invoice_paid_chan_recv)


async def wait_for_paid_invoices(invoice_paid_chan: trio.MemoryReceiveChannel):
    async for payment in invoice_paid_chan:
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "lnsubdomain" != payment.extra.get("tag"):
        # not an lnurlp invoice
        return

    await payment.set_pending(False)
    subdomain = await set_subdomain_paid(payment_hash=payment.payment_hash)
    domain = await get_domain(subdomain.domain)

    ### Create subdomain
    cf_response = cloudflare_create_subdomain(
        domain=domain,
        subdomain=subdomain.subdomain,
        record_type=subdomain.record_type,
        ip=subdomain.ip,
    )

    ### Use webhook to notify about cloudflare registration
    if domain.webhook:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    domain.webhook,
                    json={
                        "domain": subdomain.domain_name,
                        "subdomain": subdomain.subdomain,
                        "record_type": subdomain.record_type,
                        "email": subdomain.email,
                        "ip": subdomain.ip,
                        "cost:": str(subdomain.sats) + " sats",
                        "duration": str(subdomain.duration) + " days",
                        "cf_response": cf_response,
                    },
                    timeout=40,
                )
            except AssertionError:
                webhook = None
