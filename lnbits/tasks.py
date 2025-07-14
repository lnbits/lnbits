import asyncio
import time
from datetime import datetime, timezone
import traceback
import uuid
from collections.abc import Coroutine
from typing import (
    Callable,
    Optional,
)

from bolt11 import Bolt11, Tags
from bolt11 import encode as bolt11_encode

from loguru import logger

from lnbits.core.crud import (
    get_standalone_offer,
    update_offer_used,
    create_payment,
    get_payments,
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
def register_invoice_listener(send_chan: asyncio.Queue, name: Optional[str] = None):
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
            await func()
            await asyncio.sleep(interval_seconds)

    return wrapper


async def invoice_callback_dispatcher(checking_id: str, is_internal: bool = False):
    """
    Takes an incoming payment, checks its status, and dispatches it to
    invoice_listeners from core and extensions.
    """
    payment = await get_standalone_payment(checking_id, incoming=True)
    if payment:
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
    else:
        funding_source = get_funding_source()
        invoice_status = await funding_source.get_invoice_extended_status(checking_id)
        logger.debug(f"Returned extended invoice status is {invoice_status}")

        # If the invoice has been found and has been either successfully externally paid, or'
        # it is a pending internal invoice
        if invoice_status and (invoice_status.success or (invoice_status.pending and is_internal)):
            logger.info(f"Invoice extended status successfully recovered for invoice {checking_id}")

            if invoice_status.offer_id:
                offer = await get_standalone_offer(invoice_status.offer_id)

                if not offer:
                    logger.warning(f"No offer found for '{invoice_status.offer_id}'.")
                    return

               logger.info(f"Offer {invoice_status.offer_id} was found in db") 
               data = await funding_source.decode_invoice(invoice_status.string)

               if not data:
                   logger.error(f"Invoice {checking_id} could not be decoded")
               elif not data.offer_id:
                   logger.error(f"Decoded invoice {checking_id} does not have an offer_id")
               elif data.offer_id != invoice_status.offer_id:
                   logger.error(f"The offer_id for decoded invoice {checking_id} ({data.offer_id}) does not match the offer_id from the invoice's extended status ({invoice_status.offer_id})")
               else:
                   description = data.description or f"Offer {data.offer_id} payment" if data.offer_id else f"Payment for invoice {data.payment_hash}"
                   create_payment_model = CreatePayment(
                       wallet_id=offer.wallet_id,
                       bolt11=data.bolt11,
                       payment_hash=data.payment_hash,
                       preimage=invoice_status.payment_preimage,
                       amount_msat=data.amount_msat,
                       offer_id=data.offer_id,
                       expiry=data.invoice_created_at+data.invoice_relative_expiry if data.invoice_relative_expiry else None,
                       memo=description,
                   )

                   if offer.is_unused:
                       await update_offer_used(data.offer_id, True)

                   payment = await create_payment(
                       checking_id=checking_id,
                       data=create_payment_model,
                       created_at=data.invoice_created_at,
                       updated_at=invoice_status.paid_at or datetime.now(timezone.utc),
                       status = PaymentState.SUCCESS
                   )

                   internal = "internal" if is_internal else ""
                   logger.success(f"{internal} invoice {checking_id} settled")
                   for name, send_chan in invoice_listeners.items():
                       logger.trace(f"invoice listeners: sending to `{name}`")
                       await send_chan.put(payment)
