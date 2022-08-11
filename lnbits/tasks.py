import asyncio
import time
import traceback
from http import HTTPStatus
from typing import Callable, List, Dict

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


class SseListenersDict(dict):
    def __init__(self, name: str = None):
        self.name = name or "sse_listener"

    def __setitem__(self, key, value):
        assert key not in self, f"{key} already in {self.name}"
        assert value not in self.values(), f"{value} already in {self.name}"
        assert type(key) == str, f"{key} is not a string"
        assert type(value) == asyncio.Queue, f"{value} is not an asyncio.Queue"
        logger.debug(f"adding sse listener to {self.name}. len = {len(self)+1}")
        return dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        logger.debug(f"removing sse listener from {self.name}. len = {len(self)-1}")
        return dict.__delitem__(self, key)


invoice_listeners: Dict[str, asyncio.Queue] = SseListenersDict("invoice_listeners")


def register_invoice_listener(send_chan: asyncio.Queue, name: str = "no_name"):
    """
    A method intended for extensions to call when they want to be notified about
    new invoice payments incoming.
    """
    logger.debug(f"registering invoice listener {name}")
    invoice_listeners[name] = send_chan


async def webhook_handler():
    handler = getattr(WALLET, "webhook_listener", None)
    if handler:
        return await handler()
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


internal_invoice_queue: asyncio.Queue = asyncio.Queue(0)


async def internal_invoice_listener():
    while True:
        checking_id = await internal_invoice_queue.get()
        logger.info("> got internal payment notification", checking_id)
        asyncio.create_task(invoice_callback_dispatcher(checking_id))


async def invoice_listener():
    async for checking_id in WALLET.paid_invoices_stream():
        logger.info("> got a payment notification", checking_id)
        asyncio.create_task(invoice_callback_dispatcher(checking_id))


async def check_pending_payments():
    outgoing = True
    incoming = True

    while True:
        for payment in await get_payments(
            since=(int(time.time()) - 60 * 60 * 24 * 15),  # 15 days ago
            complete=False,
            pending=True,
            outgoing=outgoing,
            incoming=incoming,
            exclude_uncheckable=True,
        ):
            await payment.check_pending()

        # we delete expired invoices once upon the first pending check
        if incoming:
            await delete_expired_invoices()
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
        logger.debug(f"sending invoice callback for payment {checking_id}")
        await payment.set_pending(False)
        for chan_name, send_chan in invoice_listeners.items():
            logger.debug(f"sending to chan: {chan_name}")
            await send_chan.put(payment)
