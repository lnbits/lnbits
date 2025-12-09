import asyncio
import traceback
import uuid
from collections.abc import Callable, Coroutine

from loguru import logger

from lnbits.core.crud import (
    get_standalone_payment,
    update_payment,
)
from lnbits.core.models import Payment, PaymentState
from lnbits.core.services.fiat_providers import handle_fiat_payment_confirmation
from lnbits.settings import settings
from lnbits.wallets import get_funding_source

tasks: list[asyncio.Task] = []
unique_tasks: dict[str, asyncio.Task] = {}


def create_task(coro: Coroutine) -> asyncio.Task:
    task = asyncio.create_task(coro)
    tasks.append(task)
    return task


def create_unique_task(name: str, coro: Coroutine) -> asyncio.Task:
    if unique_tasks.get(name):
        logger.warning(f"task `{name}` already exists, cancelling it")
        try:
            unique_tasks[name].cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task `{name}`: {exc!s}")
    task = asyncio.create_task(coro)
    unique_tasks[name] = task
    return task


def create_permanent_task(func: Callable[[], Coroutine]) -> asyncio.Task:
    return create_task(catch_everything_and_restart(func))


def create_permanent_unique_task(
    name: str, coro: Callable[[], Coroutine]
) -> asyncio.Task:
    return create_unique_task(name, catch_everything_and_restart(coro, name))


def cancel_all_tasks() -> None:
    for task in tasks:
        try:
            task.cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task: {exc!s}")
    for name, task in unique_tasks.items():
        try:
            task.cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task `{name}`: {exc!s}")


async def catch_everything_and_restart(
    func: Callable[[], Coroutine],
    name: str = "unnamed",
) -> Coroutine:
    try:
        return await func()
    except asyncio.CancelledError:
        raise  # because we must pass this up
    except Exception as exc:
        logger.error(f"exception in background task `{name}`:", exc)
        logger.error(traceback.format_exc())
        logger.error("will restart the task in 5 seconds.")
        await asyncio.sleep(5)
        return await catch_everything_and_restart(func, name)


invoice_listeners: dict[str, asyncio.Queue] = {}


# TODO: name should not be optional
# some extensions still dont use a name, but they should
def register_invoice_listener(send_chan: asyncio.Queue, name: str | None = None):
    """
    A method intended for extensions (and core/tasks.py) to call when they want to be
    notified about new invoice payments incoming. Will emit all incoming payments.
    """
    if not name:
        # fallback to a random name if extension didn't provide one
        name = f"no_name_{str(uuid.uuid4())[:8]}"

    if invoice_listeners.get(name):
        logger.warning(f"invoice listener `{name}` already exists, replacing it")

    logger.trace(f"registering invoice listener `{name}`")
    invoice_listeners[name] = send_chan


internal_invoice_queue: asyncio.Queue = asyncio.Queue(0)


async def internal_invoice_queue_put(checking_id: str) -> None:
    """
    A method to call when it wants to notify about an internal invoice payment.
    """
    await internal_invoice_queue.put(checking_id)


async def internal_invoice_listener() -> None:
    """
    internal_invoice_queue will be filled directly in core/services.py
    after the payment was deemed to be settled internally.

    Called by the app startup sequence.
    """
    while settings.lnbits_running:
        checking_id = await internal_invoice_queue.get()
        logger.info(f"got an internal payment notification {checking_id}")
        await invoice_callback_dispatcher(checking_id, is_internal=True)


async def invoice_listener() -> None:
    """
    invoice_listener will collect all invoices that come directly
    from the backend wallet.

    Called by the app startup sequence.
    """
    funding_source = get_funding_source()
    async for checking_id in funding_source.paid_invoices_stream():
        logger.info(f"got a payment notification {checking_id}")
        await invoice_callback_dispatcher(checking_id)


def wait_for_paid_invoices(
    invoice_listener_name: str,
    func: Callable[[Payment], Coroutine],
) -> Callable[[], Coroutine]:

    async def wrapper() -> None:
        invoice_queue: asyncio.Queue = asyncio.Queue()
        register_invoice_listener(invoice_queue, invoice_listener_name)
        while settings.lnbits_running:
            payment = await invoice_queue.get()
            await func(payment)

    return wrapper


def run_interval(
    interval_seconds: int,
    func: Callable[[], Coroutine],
) -> Callable[[], Coroutine]:
    """Run a function at a specified interval in seconds, while the server is running"""

    async def wrapper() -> None:
        while settings.lnbits_running:
            try:
                await func()
            except Exception as e:
                logger.error(f"Error occurred in interval task: {e}")
                logger.warning(traceback.format_exc())
            await asyncio.sleep(interval_seconds)

    return wrapper


async def invoice_callback_dispatcher(checking_id: str, is_internal: bool = False):
    """
    Takes an incoming payment, checks its status, and dispatches it to
    invoice_listeners from core and extensions.
    """
    payment = await get_standalone_payment(checking_id, incoming=True)
    if not payment:
        logger.warning(f"No payment found for '{checking_id}'.")
        return
    if not payment.is_in:
        logger.warning(f"Payment '{checking_id}' is not incoming, skipping.")
        return

    status = await payment.check_status(skip_internal_payment_notifications=True)
    payment.fee = status.fee_msat or payment.fee
    # only overwrite preimage if status.preimage provides it
    payment.preimage = status.preimage or payment.preimage
    payment.status = PaymentState.SUCCESS
    await update_payment(payment)
    if payment.fiat_provider:
        await handle_fiat_payment_confirmation(payment)
    internal = "internal" if is_internal else ""
    logger.success(f"{internal} invoice {checking_id} settled")
    for name, send_chan in invoice_listeners.items():
        logger.trace(f"invoice listeners: sending to `{name}`")
        await send_chan.put(payment)
