import asyncio

import httpx
from loguru import logger

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener, register_payment_listener

from .crud import get_hedges
from ...helpers import get_current_extension_name


async def wait_for_sent_payments():
    payment_queue = asyncio.Queue()
    register_payment_listener(payment_queue, get_current_extension_name())

    logger.info("> hedge plugin is ready for accepting callbacks")
    while True:
        payment = await payment_queue.get()
        await on_payment_settled(payment)


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    logger.info("> hedge plugin is ready for accepting callbacks")
    while True:
        payment = await invoice_queue.get()
        await on_payment_settled(payment)


async def on_payment_settled(payment: Payment) -> None:
    hedge = await get_hedges(wallet_id=payment.wallet_id)
    if not hedge:
        # no registered hedge settings
        return

    host = hedge[0].hedgeuri
    wallet = payment.wallet_id
    sats = int(payment.amount / 1000)
    rate = 0

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                host + "/state",
                timeout=40,
            )
            res = r.json()
            rate = int(100.0e6 / res["ticker"])
        except Exception as e:
            logger.error(f"caught exception {e} while requesting rate")
            return await mark_webhook_sent(payment, -1)

        logger.info(f"> hedging payment {sats}@{rate} for wallet {wallet}")

        try:
            r = await client.post(
                host + "/hedge/htlc",
                json={
                    "channel_id": wallet,
                    "sats": sats,
                    "rate": rate,
                },
                timeout=40,
            )
            return await mark_webhook_sent(payment, r.status_code)
        except (httpx.ConnectError, httpx.RequestError) as e:
            logger.error(f"caught exception {e} while hedging")

        return await mark_webhook_sent(payment, -1)


async def mark_webhook_sent(payment: Payment, status: int) -> None:
    """
    Currently only prints out information about payment
    """
    logger.info(f"> mark_webhook_sent {payment.payment_hash} status {status}")
