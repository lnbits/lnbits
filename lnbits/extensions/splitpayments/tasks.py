import json

from lnbits.core.models import Payment
from lnbits.core.crud import create_payment
from lnbits.core import db as core_db
from lnbits.tasks import register_invoice_listener, internal_invoice_queue
from lnbits.helpers import urlsafe_short_hash

from .crud import get_targets


import asyncio
import httpx

from lnbits.core import db as core_db
from lnbits.core.models import Payment


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "splitpayments" == payment.extra.get("tag") or payment.extra.get("splitted"):
        # already splitted, ignore
        return

    # now we make some special internal transfers (from no one to the receiver)
    targets = await get_targets(payment.wallet_id)
    transfers = [
        (target.wallet, int(target.percent * payment.amount / 100))
        for target in targets
    ]
    transfers = [(wallet, amount) for wallet, amount in transfers if amount > 0]
    amount_left = payment.amount - sum([amount for _, amount in transfers])

    if amount_left < 0:
        print("splitpayments failure: amount_left is negative.", payment.payment_hash)
        return

    if not targets:
        return

    # mark the original payment with one extra key, "splitted"
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
            json.dumps(dict(**payment.extra, splitted=True)),
            amount_left,
            payment.payment_hash,
        ),
    )

    # perform the internal transfer using the same payment_hash
    for wallet, amount in transfers:
        internal_checking_id = f"internal_{urlsafe_short_hash()}"
        await create_payment(
            wallet_id=wallet,
            checking_id=internal_checking_id,
            payment_request="",
            payment_hash=payment.payment_hash,
            amount=amount,
            memo=payment.memo,
            pending=False,
            extra={"tag": "splitpayments"},
        )

        # manually send this for now
    await internal_invoice_queue.put(internal_checking_id)
    return
