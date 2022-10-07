import asyncio
import json
from http import HTTPStatus
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from lnbits import bolt11
from lnbits.core.models import Payment
from lnbits.core.services import pay_invoice
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_lnurldevice, get_lnurldevicepayment, update_lnurldevicepayment
from .views import updater


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    # (avoid loops)
    if "Switch" == payment.extra.get("tag"):
        lnurldevicepayment = await get_lnurldevicepayment(payment.extra.get("id"))
        if not lnurldevicepayment:
            return
        if lnurldevicepayment.payhash == "used":
            return
        lnurldevicepayment = await update_lnurldevicepayment(
            lnurldevicepayment_id=payment.extra.get("id"), payhash="used"
        )
        return await updater(lnurldevicepayment.deviceid)
    return
