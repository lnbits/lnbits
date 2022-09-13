import asyncio
import time
import traceback
from http import HTTPStatus
from typing import Callable, List

from fastapi.exceptions import HTTPException
from loguru import logger

from lnbits.core.crud import (
    delete_expired_invoices,
    get_balance_checks,
    get_payments,
    get_standalone_payment,
)
from lnbits.core.services import redeem_lnurl_withdraw
from lnbits.settings import WALLET

from .core import db

deferred_async: List[Callable] = []


def record_async(func: Callable) -> Callable:
    def recorder(state):
        deferred_async.append(func)

    return recorder


async def run_deferred_async():
    for func in deferred_async:
        asyncio.create_task(catch_everything_and_restart(func))


async def catch_everything_and_restart(func):
    try:
        await func()
    except asyncio.CancelledError:
        raise  # because we must pass this up
    except Exception as exc:
        logger.error("caught exception in background task:", exc)
        logger.error(traceback.format_exc())
        logger.error("will restart the task in 5 seconds.")
        await asyncio.sleep(5)
        await catch_everything_and_restart(func)


async def send_push_promise(a, b) -> None:
    pass


invoice_listeners: List[asyncio.Queue] = []


def register_invoice_listener(send_chan: asyncio.Queue):
    """
    A method intended for extensions to call when they want to be notified about
    new invoice payments incoming.
    """
    invoice_listeners.append(send_chan)


async def webhook_handler():
    handler = getattr(WALLET, "webhook_listener", None)
    if handler:
        return await handler()
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


internal_invoice_queue: asyncio.Queue = asyncio.Queue(0)


async def internal_invoice_listener():
    while True:
        checking_id = await internal_invoice_queue.get()
        asyncio.create_task(invoice_callback_dispatcher(checking_id))


async def invoice_listener():
    async for checking_id in WALLET.paid_invoices_stream():
        logger.info("> got a payment notification", checking_id)
        asyncio.create_task(invoice_callback_dispatcher(checking_id))


async def check_pending_payments():
    outgoing = True
    incoming = True

    while True:
        async with db.connect() as conn:
            logger.debug(
                f"Task: checking all pending payments (incoming={incoming}, outgoing={outgoing}) of last 15 days"
            )
            start_time: float = time.time()
            pending_payments = await get_payments(
                since=(int(time.time()) - 60 * 60 * 24 * 15),  # 15 days ago
                complete=False,
                pending=True,
                outgoing=outgoing,
                incoming=incoming,
                exclude_uncheckable=True,
                conn=conn,
            )
            for payment in pending_payments:
                await payment.check_status(conn=conn)

            logger.debug(
                f"Task: pending check finished for {len(pending_payments)} payments (took {time.time() - start_time:0.3f} s)"
            )
            # we delete expired invoices once upon the first pending check
            if incoming:
                logger.debug("Task: deleting all expired invoices")
                start_time: float = time.time()
                await delete_expired_invoices(conn=conn)
                logger.debug(
                    f"Task: expired invoice deletion finished (took {time.time() - start_time:0.3f} s)"
                )

        # after the first check we will only check outgoing, not incoming
        # that will be handled by the global invoice listeners, hopefully
        incoming = False

        await asyncio.sleep(60 * 30)  # every 30 minutes


async def perform_balance_checks():
    while True:
        for bc in await get_balance_checks():
            redeem_lnurl_withdraw(bc.wallet, bc.url)

        await asyncio.sleep(60 * 60 * 6)  # every 6 hours


async def invoice_callback_dispatcher(checking_id: str):
    payment = await get_standalone_payment(checking_id, incoming=True)
    if payment and payment.is_in:
        logger.trace("sending invoice callback for payment", checking_id)
        await payment.set_pending(False)
        for send_chan in invoice_listeners:
            await send_chan.put(payment)
