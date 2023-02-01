import asyncio

from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_livestream_by_track, get_producer, get_track


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:

    if payment.extra.get("tag") != "livestream":
        # not a livestream invoice
        return

    track = await get_track(payment.extra.get("track", -1))
    if not track:
        logger.error("this should never happen", payment)
        return

    if payment.extra.get("shared_with"):
        logger.error("payment was shared already", payment)
        return

    producer = await get_producer(track.producer)
    assert producer, f"track {track.id} is not associated with a producer"

    ls = await get_livestream_by_track(track.id)
    assert ls, f"track {track.id} is not associated with a livestream"

    amount = int(payment.amount * (100 - ls.fee_pct) / 100)

    payment_hash, payment_request = await create_invoice(
        wallet_id=producer.wallet,
        amount=int(amount / 1000),
        internal=True,
        memo=f"Revenue from '{track.name}'.",
    )
    logger.debug(
        f"livestream: producer invoice created: {payment_hash}, {amount} msats"
    )

    checking_id = await pay_invoice(
        payment_request=payment_request,
        wallet_id=payment.wallet_id,
        extra={
            **payment.extra,
            "shared_with": f"Producer ID: {producer.id}",
            "received": payment.amount,
        },
    )
    logger.debug(f"livestream: producer invoice paid: {checking_id}")

    # so the flow is the following:
    # - we receive, say, 1000 satoshis
    # - if the fee_pct is, say, 30%, the amount we will send is 700
    # - we change the amount of receiving payment on the database from 1000 to 300
    # - we create a new payment on the producer's wallet with amount 700
