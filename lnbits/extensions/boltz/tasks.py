import asyncio

import httpx
from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import check_transaction_status
from lnbits.tasks import register_invoice_listener

from .boltz import (
    create_claim_tx,
    create_refund_tx,
    get_swap_status,
    start_confirmation_listener,
    start_onchain_listener,
)
from .crud import (
    get_all_pending_reverse_submarine_swaps,
    get_all_pending_submarine_swaps,
    get_reverse_submarine_swap,
    get_submarine_swap,
    update_swap_status,
)

"""
testcases for boltz startup
A. normal swaps
  1. test: create -> kill -> start -> startup invoice listeners -> pay onchain funds -> should complete
  2. test: create -> kill -> pay onchain funds -> start -> startup check  -> should complete
  3. test: create -> kill -> mine blocks and hit timeout -> start -> should go timeout/failed
  4. test: create -> kill -> pay to less onchain funds -> mine blocks hit timeout -> start lnbits -> should be refunded

B. reverse swaps
  1. test: create instant -> kill -> boltz does lockup -> not confirmed -> start lnbits -> should claim/complete
  2. test: create instant -> kill -> no lockup -> start lnbits -> should start onchain listener -> boltz does lockup -> should claim/complete (difficult to test)
  3. test: create -> kill -> boltz does lockup -> not confirmed -> start lnbits -> should start tx listener -> after confirmation -> should claim/complete
  4. test: create -> kill -> boltz does lockup -> confirmed -> start lnbits -> should claim/complete
  5. test: create -> kill -> boltz does lockup -> hit timeout -> boltz refunds -> start -> should timeout
"""


async def check_for_pending_swaps():
    try:
        swaps = await get_all_pending_submarine_swaps()
        reverse_swaps = await get_all_pending_reverse_submarine_swaps()
        if len(swaps) > 0 or len(reverse_swaps) > 0:
            logger.debug(f"Boltz - startup swap check")
    except:
        # database is not created yet, do nothing
        return

    if len(swaps) > 0:
        logger.debug(f"Boltz - {len(swaps)} pending swaps")
        for swap in swaps:
            try:
                swap_status = get_swap_status(swap)
                # should only happen while development when regtest is reset
                if swap_status.exists is False:
                    logger.warning(f"Boltz - swap: {swap.boltz_id} does not exist.")
                    await update_swap_status(swap.id, "failed")
                    continue

                payment_status = await check_transaction_status(
                    swap.wallet, swap.payment_hash
                )

                if payment_status.paid:
                    logger.debug(
                        f"Boltz - swap: {swap.boltz_id} got paid while offline."
                    )
                    await update_swap_status(swap.id, "complete")
                else:
                    if swap_status.hit_timeout:
                        if not swap_status.has_lockup:
                            logger.warning(
                                f"Boltz - swap: {swap.id} hit timeout, but no lockup tx..."
                            )
                            await update_swap_status(swap.id, "timeout")
                        else:
                            logger.debug(f"Boltz - refunding swap: {swap.id}...")
                            await create_refund_tx(swap)
                            await update_swap_status(swap.id, "refunded")

            except Exception as exc:
                logger.error(f"Boltz - swap: {swap.id} - {str(exc)}")

    if len(reverse_swaps) > 0:
        logger.debug(f"Boltz - {len(reverse_swaps)} pending reverse swaps")
        for reverse_swap in reverse_swaps:
            try:
                swap_status = get_swap_status(reverse_swap)

                if swap_status.exists is False:
                    logger.debug(
                        f"Boltz - reverse_swap: {reverse_swap.boltz_id} does not exist."
                    )
                    await update_swap_status(reverse_swap.id, "failed")
                    continue

                # if timeout hit, boltz would have already refunded
                if swap_status.hit_timeout:
                    logger.debug(
                        f"Boltz - reverse_swap: {reverse_swap.boltz_id} timeout."
                    )
                    await update_swap_status(reverse_swap.id, "timeout")
                    continue

                if not swap_status.has_lockup:
                    # start listener for onchain address
                    logger.debug(
                        f"Boltz - reverse_swap: {reverse_swap.boltz_id} restarted onchain address listener."
                    )
                    await start_onchain_listener(reverse_swap)
                    continue

                if reverse_swap.instant_settlement or swap_status.confirmed:
                    await create_claim_tx(reverse_swap, swap_status.lockup)
                else:
                    logger.debug(
                        f"Boltz - reverse_swap: {reverse_swap.boltz_id} restarted confirmation listener."
                    )
                    await start_confirmation_listener(reverse_swap, swap_status.lockup)

            except Exception as exc:
                logger.error(f"Boltz - reverse swap: {reverse_swap.id} - {str(exc)}")


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if "boltz" != payment.extra.get("tag"):
        # not a boltz invoice
        return

    await payment.set_pending(False)
    swap_id = payment.extra.get("swap_id")
    swap = await get_submarine_swap(swap_id)

    if not swap:
        logger.error(f"swap_id: {swap_id} not found.")
        return

    logger.info(
        f"Boltz - lightning invoice is paid, normal swap completed. swap_id: {swap_id}"
    )
    await update_swap_status(swap_id, "complete")
