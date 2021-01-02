from http import HTTPStatus
from quart.json import jsonify
import trio  # type: ignore
import json
import httpx

from .crud import get_domain, set_subdomain_paid
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


async def on_invoice_paid(payment: Payment) -> None:
    print(payment)
    if "lnsubdomain" != payment.extra.get("tag"):
        # not an lnurlp invoice
        return

    wallet = await get_wallet(payment.wallet_id)
    await payment.set_pending(False)
    subdomain = await set_subdomain_paid(payment_hash=payment.payment_hash)
    domain = await get_domain(subdomain.domain)

    ### SEND REQUEST TO CLOUDFLARE
    url = "https://api.cloudflare.com/client/v4/zones/" + domain.cf_zone_id + "/dns_records"
    header = {"Authorization": "Bearer " + domain.cf_token, "Content-Type": "application/json"}
    aRecord = subdomain.subdomain + "." + subdomain.domain_name
    cf_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                headers=header,
                json={
                    "type": subdomain.record_type,
                    "name": aRecord,
                    "content": subdomain.ip,
                    "ttl": 0,
                    "proxed": False,
                },
                timeout=40,
            )
            cf_response = r.text
        except AssertionError:
            cf_response = "Error occured"

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

    return jsonify({"paid": True}), HTTPStatus.OK
