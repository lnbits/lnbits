import asyncio

import httpx
from loguru import logger

from lnbits.core.models import Payment
from lnbits.extensions.satspay.crud import check_address_balance, get_charge
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .helpers import public_charge
from .models import Charges


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "charge":
        # not a charge invoice
        return

    charge = await get_charge(payment.memo)
    if not charge:
        logger.error("this should never happen", payment)
        return

    await payment.set_pending(False)
    charge = await check_address_balance(charge_id=charge.id)

    if charge.paid and charge.webhook:
        await call_webhook(charge)


async def call_webhook(charge: Charges):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                charge.webhook,
                json=public_charge(charge),
                timeout=40,
            )
        except AssertionError:
            charge.webhook = None
        except Exception as e:
            logger.warning(f"Failed to call webhook for charge {charge.id}")
            logger.warning(e)
