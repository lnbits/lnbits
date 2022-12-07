import asyncio

from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice, websocketUpdater
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_tpos


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "tpos":
        return

    tpos = await get_tpos(payment.extra.get("tposId"))
    tipAmount = payment.extra.get("tipAmount")

    strippedPayment = {
        "amount": payment.amount,
        "fee": payment.fee,
        "checking_id": payment.checking_id,
        "payment_hash": payment.payment_hash,
        "bolt11": payment.bolt11,
    }

    await websocketUpdater(payment.extra.get("tposId"), str(strippedPayment))

    if tipAmount is None:
        # no tip amount
        return

    payment_hash, payment_request = await create_invoice(
        wallet_id=tpos.tip_wallet,
        amount=int(tipAmount),  # sats
        internal=True,
        memo=f"tpos tip",
    )
    logger.debug(f"tpos: tip invoice created: {payment_hash}")

    checking_id = await pay_invoice(
        payment_request=payment_request,
        wallet_id=payment.wallet_id,
        extra={"tag": "tpos"},
    )
    logger.debug(f"tpos: tip invoice paid: {checking_id}")
