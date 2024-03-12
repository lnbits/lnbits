import asyncio
from typing import Dict

import httpx
from loguru import logger

from lnbits.core.crud import (
    get_balance_notify,
    get_wallet,
    get_webpush_subscriptions_for_user,
    mark_webhook_sent,
)
from lnbits.core.models import Payment
from lnbits.core.services import (
    get_balance_delta,
    send_payment_notification,
    switch_to_voidwallet,
)
from lnbits.settings import get_wallet_class, settings
from lnbits.tasks import (
    create_permanent_task,
    create_task,
    register_invoice_listener,
    send_push_notification,
)

api_invoice_listeners: Dict[str, asyncio.Queue] = {}


def register_killswitch():
    """
    Registers a killswitch which will check lnbits-status repository for a signal from
    LNbits and will switch to VoidWallet if the killswitch is triggered.
    """
    logger.debug("Starting killswitch task")
    create_permanent_task(killswitch_task)


async def killswitch_task():
    while True:
        WALLET = get_wallet_class()
        if settings.lnbits_killswitch and WALLET.__class__.__name__ != "VoidWallet":
            with httpx.Client() as client:
                try:
                    r = client.get(settings.lnbits_status_manifest, timeout=4)
                    r.raise_for_status()
                    if r.status_code == 200:
                        ks = r.json().get("killswitch")
                        if ks and ks == 1:
                            logger.error(
                                "Switching to VoidWallet. Killswitch triggered."
                            )
                            await switch_to_voidwallet()
                except (httpx.RequestError, httpx.HTTPStatusError):
                    logger.error(
                        "Cannot fetch lnbits status manifest."
                        f" {settings.lnbits_status_manifest}"
                    )
        await asyncio.sleep(settings.lnbits_killswitch_interval * 60)


async def register_watchdog():
    """
    Registers a watchdog which will check lnbits balance and nodebalance
    and will switch to VoidWallet if the watchdog delta is reached.
    """
    # TODO: implement watchdog properly
    # logger.debug("Starting watchdog task")
    # create_permanent_task(watchdog_task)


async def watchdog_task():
    while True:
        WALLET = get_wallet_class()
        if settings.lnbits_watchdog and WALLET.__class__.__name__ != "VoidWallet":
            try:
                delta, *_ = await get_balance_delta()
                logger.debug(f"Running watchdog task. current delta: {delta}")
                if delta + settings.lnbits_watchdog_delta <= 0:
                    logger.error(f"Switching to VoidWallet. current delta: {delta}")
                    await switch_to_voidwallet()
            except Exception as e:
                logger.error("Error in watchdog task", e)
        await asyncio.sleep(settings.lnbits_watchdog_interval * 60)


def register_task_listeners():
    """
    Registers an invoice listener queue for the core tasks. Incoming payments in this
    queue will eventually trigger the signals sent to all other extensions
    and fulfill other core tasks such as dispatching webhooks.
    """
    invoice_paid_queue = asyncio.Queue(5)
    # we register invoice_paid_queue to receive all incoming invoices
    register_invoice_listener(invoice_paid_queue, "core/tasks.py")
    # register a worker that will react to invoices
    create_task(wait_for_paid_invoices(invoice_paid_queue))


async def wait_for_paid_invoices(invoice_paid_queue: asyncio.Queue):
    """
    This worker dispatches events to all extensions,
    dispatches webhooks and balance notifys.
    """
    while True:
        payment = await invoice_paid_queue.get()
        logger.trace("received invoice paid event")
        # send information to sse channel
        await dispatch_api_invoice_listeners(payment)
        wallet = await get_wallet(payment.wallet_id)
        if wallet:
            await send_payment_notification(wallet, payment)
        # dispatch webhook
        if payment.webhook and not payment.webhook_status:
            await dispatch_webhook(payment)

        # dispatch balance_notify
        url = await get_balance_notify(payment.wallet_id)
        if url:
            headers = {"User-Agent": settings.user_agent}
            async with httpx.AsyncClient(headers=headers) as client:
                try:
                    r = await client.post(url, timeout=4)
                    r.raise_for_status()
                    await mark_webhook_sent(payment.payment_hash, r.status_code)
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    await mark_webhook_sent(payment.payment_hash, status_code)
                    logger.warning(
                        f"balance_notify returned a bad status_code: {status_code} "
                        f"while requesting {exc.request.url!r}."
                    )
                    logger.warning(exc)
                except httpx.RequestError as exc:
                    await mark_webhook_sent(payment.payment_hash, -1)
                    logger.warning(f"Could not send balance_notify to {url}")
                    logger.warning(exc)

        await send_payment_push_notification(payment)


async def dispatch_api_invoice_listeners(payment: Payment):
    """
    Emits events to invoice listener subscribed from the API.
    """
    for chan_name, send_channel in api_invoice_listeners.items():
        try:
            logger.debug(f"sending invoice paid event to {chan_name}")
            send_channel.put_nowait(payment)
        except asyncio.QueueFull:
            logger.error(f"removing sse listener {send_channel}:{chan_name}")
            api_invoice_listeners.pop(chan_name)


async def dispatch_webhook(payment: Payment):
    """
    Dispatches the webhook to the webhook url.
    """
    logger.debug("sending webhook", payment.webhook)

    if not payment.webhook:
        return await mark_webhook_sent(payment.payment_hash, -1)

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers) as client:
        data = payment.dict()
        try:
            r = await client.post(payment.webhook, json=data, timeout=40)
            r.raise_for_status()
            await mark_webhook_sent(payment.payment_hash, r.status_code)
        except httpx.HTTPStatusError as exc:
            await mark_webhook_sent(payment.payment_hash, exc.response.status_code)
            logger.warning(
                f"webhook returned a bad status_code: {exc.response.status_code} "
                f"while requesting {exc.request.url!r}."
            )
        except httpx.RequestError:
            await mark_webhook_sent(payment.payment_hash, -1)
            logger.warning(f"Could not send webhook to {payment.webhook}")


async def send_payment_push_notification(payment: Payment):
    wallet = await get_wallet(payment.wallet_id)

    if wallet:
        subscriptions = await get_webpush_subscriptions_for_user(wallet.user)

        amount = int(payment.amount / 1000)

        title = f"LNbits: {wallet.name}"
        body = f"You just received {amount} sat{'s'[:amount^1]}!"

        if payment.memo:
            body += f"\r\n{payment.memo}"

        for subscription in subscriptions:
            # todo: review permissions when user-id-only not allowed
            # todo: replace all this logic with websockets?
            url = (
                f"https://{subscription.host}/wallet?usr={wallet.user}&wal={wallet.id}"
            )
            await send_push_notification(subscription, title, body, url)
