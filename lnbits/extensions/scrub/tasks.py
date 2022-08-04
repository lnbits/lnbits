import asyncio
import json
from http import HTTPStatus
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from lnbits import bolt11
from lnbits.core.models import Payment
from lnbits.core.services import pay_invoice
from lnbits.tasks import register_invoice_listener

from .crud import get_scrub_by_wallet


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    # (avoid loops)
    if "scrubed" == payment.extra.get("tag"):
        # already scrubbed
        return

    scrub_link = await get_scrub_by_wallet(payment.wallet_id)

    if not scrub_link:
        return

    from lnbits.core.views.api import api_lnurlscan

    # DECODE LNURLP OR LNADDRESS
    data = await api_lnurlscan(scrub_link.payoraddress)

    # I REALLY HATE THIS DUPLICATION OF CODE!! CORE/VIEWS/API.PY, LINE 267
    domain = urlparse(data["callback"]).netloc

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                data["callback"],
                params={"amount": payment.amount},
                timeout=40,
            )
            if r.is_error:
                raise httpx.ConnectError
        except (httpx.ConnectError, httpx.RequestError):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Failed to connect to {domain}.",
            )

    params = json.loads(r.text)
    if params.get("status") == "ERROR":
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} said: '{params.get('reason', '')}'",
        )

    invoice = bolt11.decode(params["pr"])
    if invoice.amount_msat != payment.amount:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} returned an invalid invoice. Expected {payment.amount} msat, got {invoice.amount_msat}.",
        )

    payment_hash = await pay_invoice(
        wallet_id=payment.wallet_id,
        payment_request=params["pr"],
        description=data["description"],
        extra={"tag": "scrubed"},
    )

    return {
        "payment_hash": payment_hash,
        # maintain backwards compatibility with API clients:
        "checking_id": payment_hash,
    }
