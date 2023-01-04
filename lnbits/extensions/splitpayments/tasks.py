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
    if payment.extra.get("tag") == "splitpayments":
        # already a splitted payment, ignore
        return

    targets = await get_targets(payment.wallet_id)
    logger.debug(targets)
    if not targets:
        return

    total_percent = sum([target.percent for target in targets])

    if total_percent > 100:
        logger.error("splitpayment failure: total percent adds up to more than 100%")
        return

    logger.debug(f"checking if tagged for {len(targets)} targets")
    tagged = False
    for target in targets:
        if target.tag in payment.extra:
            tagged = True
            payment_hash, payment_request = await create_invoice(
                wallet_id=target.wallet,
                amount=int(payment.amount / 1000),  # sats
                internal=True,
                memo=f"Pushed tagged payment to {target.alias}",
                extra={"tag": "splitpayments"},
            )
            logger.debug(f"created split invoice: {payment_hash}")

            checking_id = await pay_invoice(
                payment_request=payment_request,
                wallet_id=payment.wallet_id,
                extra={"tag": "splitpayments"},
            )
            logger.debug(f"paid split invoice: {checking_id}")

    logger.debug(f"performing split to {len(targets)} targets")

    if tagged == False:
        for target in targets:
            if target.percent > 0:
                amount = int(payment.amount * target.percent / 100)  # msats
                payment_hash, payment_request = await create_invoice(
                    wallet_id=target.wallet,
                    amount=int(amount / 1000),  # sats
                    internal=True,
                    memo=f"split payment: {target.percent}% for {target.alias or target.wallet}",
                    extra={"tag": "splitpayments"},
                )
                logger.debug(f"created split invoice: {payment_hash}")

                checking_id = await pay_invoice(
                    payment_request=payment_request,
                    wallet_id=payment.wallet_id,
                    extra={"tag": "splitpayments"},
                )
                logger.debug(f"paid split invoice: {checking_id}")
