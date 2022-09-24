import asyncio

import httpx

from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .cloudflare import cloudflare_create_subdomain
from .crud import get_domain, set_subdomain_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "lnsubdomain":
        # not an lnurlp invoice
        return

    await payment.set_pending(False)
    subdomain = await set_subdomain_paid(payment_hash=payment.payment_hash)
    domain = await get_domain(subdomain.domain)

    ### Create subdomain
    cf_response = await cloudflare_create_subdomain(
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
