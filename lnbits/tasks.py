import asyncio
import time
import traceback
import uuid
from http import HTTPStatus
from typing import Dict, Optional

from fastapi.exceptions import HTTPException
from loguru import logger

from lnbits.core.crud import (
    delete_expired_invoices,
    get_balance_checks,
    get_payments,
    get_standalone_payment,
)
from lnbits.core.services import redeem_lnurl_withdraw
from lnbits.wallets import get_wallet_class

from .core import db


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


class SseListenersDict(dict):
    """
    A dict of sse listeners.
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name or f"sse_listener_{str(uuid.uuid4())[:8]}"

    def __setitem__(self, key, value):
        assert type(key) == str, f"{key} is not a string"
        assert type(value) == asyncio.Queue, f"{value} is not an asyncio.Queue"
        logger.trace(f"sse: adding listener {key} to {self.name}. len = {len(self)+1}")
        return super().__setitem__(key, value)

    def __delitem__(self, key):
        logger.trace(f"sse: removing listener from {self.name}. len = {len(self)-1}")
        return super().__delitem__(key)

    _RaiseKeyError = object()  # singleton for no-default behavior

    def pop(self, key, v=_RaiseKeyError) -> None:
        logger.trace(f"sse: removing listener from {self.name}. len = {len(self)-1}")
        return super().pop(key)


invoice_listeners: Dict[str, asyncio.Queue] = SseListenersDict("invoice_listeners")


def register_invoice_listener(send_chan: asyncio.Queue, name: Optional[str] = None):
    """
    A method intended for extensions (and core/tasks.py) to call when they want to be notified about
    new invoice payments incoming. Will emit all incoming payments.
    """
    name_unique = f"{name or 'no_name'}_{str(uuid.uuid4())[:8]}"
    logger.trace(f"sse: registering invoice listener {name_unique}")
    invoice_listeners[name_unique] = send_chan


async def webhook_handler():
    """
    Returns the webhook_handler for the selected wallet if present. Used by API.
    """
    WALLET = get_wallet_class()
    handler = getattr(WALLET, "webhook_listener", None)
    if handler:
        return await handler()
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


internal_invoice_queue: asyncio.Queue = asyncio.Queue(0)


async def internal_invoice_listener():
    """
    internal_invoice_queue will be filled directly in core/services.py
    after the payment was deemed to be settled internally.

    Called by the app startup sequence.
    """
    while True:
        checking_id = await internal_invoice_queue.get()
        logger.info("> got internal payment notification", checking_id)
        asyncio.create_task(invoice_callback_dispatcher(checking_id))


async def invoice_listener():
    """
    invoice_listener will collect all invoices that come directly
    from the backend wallet.

    Called by the app startup sequence.
    """
    WALLET = get_wallet_class()
    async for checking_id in WALLET.paid_invoices_stream():
        logger.info("> got a payment notification", checking_id)
        asyncio.create_task(invoice_callback_dispatcher(checking_id))


async def check_pending_payments():
    """
    check_pending_payments is called during startup to check for pending payments with
    the backend and also to delete expired invoices. Incoming payments will be
    checked only once, outgoing pending payments will be checked regularly.
    """
    outgoing = True
    incoming = True

    while True:
        async with db.connect() as conn:
            logger.info(
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

            logger.info(
                f"Task: pending check finished for {len(pending_payments)} payments (took {time.time() - start_time:0.3f} s)"
            )
            # we delete expired invoices once upon the first pending check
            if incoming:
                logger.debug("Task: deleting all expired invoices")
                start_time: float = time.time()
                await delete_expired_invoices(conn=conn)
                logger.info(
                    f"Task: expired invoice deletion finished (took {time.time() - start_time:0.3f} s)"
                )

        # after the first check we will only check outgoing, not incoming
        # that will be handled by the global invoice listeners, hopefully
        incoming = False

        await asyncio.sleep(60 * 30)  # every 30 minutes


async def perform_balance_checks():
    while True:
        for bc in await get_balance_checks():
            await redeem_lnurl_withdraw(bc.wallet, bc.url)

        await asyncio.sleep(60 * 60 * 6)  # every 6 hours


async def invoice_callback_dispatcher(checking_id: str):
    """
    Takes incoming payments, sets pending=False, and dispatches them to
    invoice_listeners from core and extensions.
    """
    payment = await get_standalone_payment(checking_id, incoming=True)
    if payment and payment.is_in:
        logger.trace(f"sse sending invoice callback for payment {checking_id}")
        await payment.set_pending(False)
        for chan_name, send_chan in invoice_listeners.items():
            logger.trace(f"sse sending to chan: {chan_name}")
            await send_chan.put(payment)
