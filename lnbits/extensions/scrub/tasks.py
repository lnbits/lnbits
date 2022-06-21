import asyncio
import json

import httpx

from lnbits.core import db as core_db
from lnbits.core.crud import get_wallet
from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .crud import get_scrub_by_wallet, get_scrub_link
from .models import ScrubLink


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    # (avoid loops)
    if "scrub" == payment.extra.get("tag"):
        # already scrubbed
        return

    scrub_link = await get_scrub_by_wallet(payment.wallet_id)
    
    if not scrub_link:
        return

    from lnbits.core.views.api import (
        CreateLNURLData,
        api_lnurlscan,
        api_payments_pay_lnurl,
    )

    wallet = await get_wallet(wallet_id=payment.wallet_id)
    assert wallet
    
    # PAY LNURLP AND LNADDRESS
    invoice = await api_lnurlscan(scrub_link.payoraddress)
    invoice_data = CreateLNURLData(
        callback = invoice["callback"],
        description_hash = invoice["description_hash"],
        amount = payment.amount
    )
    print("INV", invoice_data, wallet)
    
    invoice_paid = await api_payments_pay_lnurl(data=invoice_data, wallet=wallet.adminkey)
    print("PAID", invoice_paid)
