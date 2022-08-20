import asyncio

import httpx
from loguru import logger

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener

from .boltz import get_swap_status
from .crud import (
    get_all_pending_reverse_submarine_swaps,
    get_all_pending_submarine_swaps,
    get_reverse_submarine_swap,
    get_submarine_swap,
    update_swap_status,
)


async def check_for_pending_swaps():

    try:
        swaps = await get_all_pending_submarine_swaps()
        reverse_swaps = await get_all_pending_reverse_submarine_swaps()
    except:
        # database is not created yet, do nothing
        return

    logger.debug(f"Boltz - startup swap check")
    logger.debug(f"Boltz - {len(swaps)} pending swaps")
    for swap in swaps:
        try:
            swap_status = get_swap_status(swap)
            logger.debug(f"Boltz - swap: {swap.id} - {swap_status.message}")
            if swap_status.exists is False:
                logger.debug(f"Boltz - swap: {swap.boltz_id} does not exist.")
                await update_swap_status(swap.id, "failed")
            if swap_status.hit_timeout is True:
                if swap_status.has_lockup is False:
                    logger.debug(
                        f"Boltz - swap: {swap.id} hit timeout, but no lockup tx..."
                    )
                    await update_swap_status(swap.id, "timeout")
                else:
                    if swap_status.is_done is True:
                        logger.debug(f"Boltz - swap: {swap.id} is already done...")
                        await update_swap_status(swap.id, "complete")
                    else:
                        if swap_status.can_refund is True:
                            logger.debug(f"Boltz - refunding swap: {swap.id}...")
        except Exception as exc:
            logger.error(f"Boltz - swap: {swap.id} - {str(exc)}")

    logger.debug(f"Boltz - {len(reverse_swaps)} pending reverse swaps")
    for reverse_swap in reverse_swaps:
        try:
            swap_status = get_swap_status(reverse_swap)
            logger.debug(
                f"Boltz - reverse_swap: {reverse_swap.id} - {swap_status.message}"
            )
            if swap_status.exists is False:
                logger.debug(
                    f"Boltz - reverse_swap: {reverse_swap.boltz_id} does not exist."
                )
                await update_swap_status(reverse_swap.id, "failed")
            if swap_status.can_refund is True:
                logger.debug(
                    f"Boltz - reverse swap: {reverse_swap.id} starting watching for onchain lockup tx again..."
                )
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
    if payment.extra.get("reverse") is not None:
        swap = await get_reverse_submarine_swap(swap_id)
    else:
        swap = await get_submarine_swap(swap_id)

    if not swap:
        logger.error(f"swap_id: {swap_id} not found. updating status failed.")
        return

    logger.info(
        f"Boltz - lightning invoice is paid, normal swap completed. swap_id: {swap_id}"
    )
    await update_swap_status(swap_id, "complete")
