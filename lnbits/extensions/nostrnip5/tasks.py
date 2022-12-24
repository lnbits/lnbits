import asyncio
import json

from lnbits.core.models import Payment
from lnbits.helpers import urlsafe_short_hash
from lnbits.tasks import internal_invoice_queue, register_invoice_listener

from .crud import activate_address


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "nostrnip5":
        # not relevant
        return

    domain_id = payment.extra.get("domain_id")
    address_id = payment.extra.get("address_id")

    print("Activating NOSTR NIP-05")
    print(domain_id)
    print(address_id)

    active = await activate_address(domain_id, address_id)

    return
