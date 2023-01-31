import asyncio
import logging
from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice, websocketUpdater
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_pegging, get_wallets, get_peggings
from .kollider_rest_client import KolliderRestClient
from .models import Pegging

log = logging.getLogger(__name__)

async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    wallets = await get_wallets("USD")
    logger.debug(f"Hedged USD wallets: {len(wallets)}")

    while True:
        payment = await invoice_queue.get()

        hedges = await get_peggings(wallet_id=payment.wallet_id)
        if not hedges:
            # no registered hedge settings
            continue

        payment.extra["peggingId"] = hedges[0].id

        await on_paid_invoice(payment)


async def on_paid_invoice(payment: Payment) -> None:
    pegging_id = payment.extra.get("peggingId")
    assert pegging_id

    pegging = await get_pegging(pegging_id)
    assert pegging


    strippedPayment = {
        "amount": payment.amount,
        "fee": payment.fee,
        "checking_id": payment.checking_id,
        "payment_hash": payment.payment_hash,
        "bolt11": payment.bolt11,
    }

    await websocketUpdater(pegging_id, str(strippedPayment))
    await update_position(pegging, payment.amount)



async def update_position(pegging: Pegging, delta_amount: int) -> None:
    client = KolliderRestClient(pegging.base_url, pegging.api_key, pegging.api_secret, pegging.api_passphrase)




"""

    payment_hash, payment_request = await create_invoice(
        wallet_id=wallet_id,
        amount=int(tipAmount),
        internal=True,
        memo=f"pegging tip",
    )
    logger.debug(f"pegging: tip invoice created: {payment_hash}")

    checking_id = await pay_invoice(
        payment_request=payment_request,
        wallet_id=payment.wallet_id,
        extra={**payment.extra, "tipSplitted": True},
    )
    logger.debug(f"pegging: tip invoice paid: {checking_id}")

"""