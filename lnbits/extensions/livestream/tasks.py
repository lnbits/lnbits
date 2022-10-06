import asyncio
import json

from loguru import logger

from lnbits.core import db as core_db
from lnbits.core.crud import create_payment
from lnbits.core.models import Payment
from lnbits.helpers import get_current_extension_name, urlsafe_short_hash
from lnbits.tasks import internal_invoice_listener, register_invoice_listener

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

    # now we make a special kind of internal transfer
    amount = int(payment.amount * (100 - ls.fee_pct) / 100)

    # mark the original payment with two extra keys, "shared_with" and "received"
    # (this prevents us from doing this process again and it's informative)
    # and reduce it by the amount we're going to send to the producer
    await core_db.execute(
        """
        UPDATE apipayments
        SET extra = ?, amount = ?
        WHERE hash = ?
          AND checking_id NOT LIKE 'internal_%'
        """,
        (
            json.dumps(
                dict(
                    **payment.extra,
                    shared_with=[producer.name, producer.id],
                    received=payment.amount,
                )
            ),
            payment.amount - amount,
            payment.payment_hash,
        ),
    )

    # perform an internal transfer using the same payment_hash to the producer wallet
    internal_checking_id = f"internal_{urlsafe_short_hash()}"
    await create_payment(
        wallet_id=producer.wallet,
        checking_id=internal_checking_id,
        payment_request="",
        payment_hash=payment.payment_hash,
        amount=amount,
        memo=f"Revenue from '{track.name}'.",
        pending=False,
    )

    # manually send this for now
    # await internal_invoice_paid.send(internal_checking_id)
    await internal_invoice_listener.put(internal_checking_id)

    # so the flow is the following:
    # - we receive, say, 1000 satoshis
    # - if the fee_pct is, say, 30%, the amount we will send is 700
    # - we change the amount of receiving payment on the database from 1000 to 300
    # - we create a new payment on the producer's wallet with amount 700
