import asyncio

from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_targets


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:

    if payment.extra.get("tag") == "splitpayments" or payment.extra.get("splitted"):
        # already a splitted payment, ignore
        return

    targets = await get_targets(payment.wallet_id)

    if not targets:
        return

    # validate target percentages
    total_percent = sum([target.percent for target in targets])

    if total_percent > 100:
        logger.error("splitpayment: total percent adds up to more than 100%")
        return
    if not all([target.percent > 0 for target in targets]):
        logger.error("splitpayment: not all percentages are positive > 0")
        return

    logger.trace(f"splitpayments: performing split payments to {len(targets)} targets")

    if payment.extra.get("amount"):
        amount_to_split = (payment.extra.get("amount") or 0) * 1000
    else:
        amount_to_split = payment.amount

    if not amount_to_split:
        logger.error("splitpayments: no amount to split")
        return

    for target in targets:
        tagged = target.tag in payment.extra
        if tagged or target.percent > 0:

        if tagged:
            memo = f"Pushed tagged payment to {target.alias}"
            amount_msat = int(amount_to_split)
        else:
            amount_msat = int(amount_to_split * target.percent / 100)
            memo = (
                f"Split payment: {target.percent}% for {target.alias or target.wallet}"
            )

        payment_hash, payment_request = await create_invoice(
            wallet_id=target.wallet,
            amount=int(amount_msat / 1000),
            internal=True,
            memo=memo,
        )

        extra = {**payment.extra, "splitted": True}

        await pay_invoice(
            payment_request=payment_request,
            wallet_id=payment.wallet_id,
            extra=extra,
        )
