import asyncio
import json
import time
import traceback
import uuid
from http import HTTPStatus
from typing import Coroutine, Dict, List, Optional

from loguru import logger
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from lnbits.core.crud import (
    delete_expired_invoices,
    delete_webpush_subscriptions,
    get_payments,
    get_standalone_payment,
)
from lnbits.settings import settings
from lnbits.wallets import get_funding_source

tasks: List[asyncio.Task] = []
unique_tasks: Dict[str, asyncio.Task] = {}


def create_task(coro):
    task = asyncio.create_task(coro)
    tasks.append(task)
    return task


def create_permanent_task(func):
    return create_task(catch_everything_and_restart(func))


def create_unique_task(name: str, coro: Coroutine):
    if unique_tasks.get(name):
        logger.warning(f"task `{name}` already exists, cancelling it")
        try:
            unique_tasks[name].cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task `{name}`: {str(exc)}")
    task = asyncio.create_task(coro)
    unique_tasks[name] = task
    return task


def create_permanent_unique_task(name: str, coro: Coroutine):
    return create_unique_task(name, catch_everything_and_restart(coro))


def cancel_all_tasks():
    for task in tasks:
        try:
            task.cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task: {str(exc)}")
    for name, task in unique_tasks.items():
        try:
            task.cancel()
        except Exception as exc:
            logger.warning(f"error while cancelling task `{name}`: {str(exc)}")


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


invoice_listeners: Dict[str, asyncio.Queue] = {}


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


async def internal_invoice_listener():
    """
    internal_invoice_queue will be filled directly in core/services.py
    after the payment was deemed to be settled internally.

    Called by the app startup sequence.
    """
    while True:
        checking_id = await internal_invoice_queue.get()
        logger.info("> got internal payment notification", checking_id)
        create_task(invoice_callback_dispatcher(checking_id))


async def invoice_listener():
    """
    invoice_listener will collect all invoices that come directly
    from the backend wallet.

    Called by the app startup sequence.
    """
    funding_source = get_funding_source()
    async for checking_id in funding_source.paid_invoices_stream():
        logger.info("> got a payment notification", checking_id)
        create_task(invoice_callback_dispatcher(checking_id))


async def check_pending_payments():
    """
    check_pending_payments is called during startup to check for pending payments with
    the backend and also to delete expired invoices. Incoming payments will be
    checked only once, outgoing pending payments will be checked regularly.
    """
    outgoing = True
    incoming = True

    while True:
        logger.info(
            f"Task: checking all pending payments (incoming={incoming},"
            f" outgoing={outgoing}) of last 15 days"
        )
        start_time = time.time()
        pending_payments = await get_payments(
            since=(int(time.time()) - 60 * 60 * 24 * 15),  # 15 days ago
            complete=False,
            pending=True,
            outgoing=outgoing,
            incoming=incoming,
            exclude_uncheckable=True,
        )
        for payment in pending_payments:
            await payment.check_status()
            await asyncio.sleep(0.01)  # to avoid complete blocking

        logger.info(
            f"Task: pending check finished for {len(pending_payments)} payments"
            f" (took {time.time() - start_time:0.3f} s)"
        )
        # we delete expired invoices once upon the first pending check
        if incoming:
            logger.debug("Task: deleting all expired invoices")
            start_time = time.time()
            await delete_expired_invoices()
            logger.info(
                "Task: expired invoice deletion finished (took"
                f" {time.time() - start_time:0.3f} s)"
            )

        # after the first check we will only check outgoing, not incoming
        # that will be handled by the global invoice listeners, hopefully
        incoming = False

        await asyncio.sleep(60 * 30)  # every 30 minutes


async def invoice_callback_dispatcher(checking_id: str):
    """
    Takes incoming payments, sets pending=False, and dispatches them to
    invoice_listeners from core and extensions.
    """
    payment = await get_standalone_payment(checking_id, incoming=True)
    if payment and payment.is_in:
        logger.trace(
            f"invoice listeners: sending invoice callback for payment {checking_id}"
        )
        await payment.set_pending(False)
        for name, send_chan in invoice_listeners.items():
            logger.trace(f"invoice listeners: sending to `{name}`")
            await send_chan.put(payment)


async def send_push_notification(subscription, title, body, url=""):
    vapid = Vapid()
    try:
        logger.debug("sending push notification")
        webpush(
            json.loads(subscription.data),
            json.dumps({"title": title, "body": body, "url": url}),
            vapid.from_pem(bytes(settings.lnbits_webpush_privkey, "utf-8")),
            {"aud": "", "sub": "mailto:alan@lnbits.com"},
        )
    except WebPushException as e:
        if e.response.status_code == HTTPStatus.GONE:
            # cleanup unsubscribed or expired push subscriptions
            await delete_webpush_subscriptions(subscription.endpoint)
        else:
            logger.error(f"failed sending push notification: {e.response.text}")
