import asyncio

import httpx
from loguru import logger

from lnbits.core.crud import (
    create_audit_entry,
    get_wallet,
    get_webpush_subscriptions_for_user,
    mark_webhook_sent,
)
from lnbits.core.crud.audit import delete_expired_audit_entries
from lnbits.core.models import AuditEntry, Payment
from lnbits.core.services import (
    get_balance_delta,
    send_payment_notification,
    switch_to_voidwallet,
)
from lnbits.settings import get_funding_source, settings
from lnbits.tasks import send_push_notification
from lnbits.utils.exchange_rates import btc_rates

audit_queue: asyncio.Queue = asyncio.Queue()


async def killswitch_task():
    """
    killswitch will check lnbits-status repository for a signal from
    LNbits and will switch to VoidWallet if the killswitch is triggered.
    """
    while settings.lnbits_running:
        funding_source = get_funding_source()
        if (
            settings.lnbits_killswitch
            and funding_source.__class__.__name__ != "VoidWallet"
        ):
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


async def watchdog_task():
    """
    Registers a watchdog which will check lnbits balance and nodebalance
    and will switch to VoidWallet if the watchdog delta is reached.
    """
    while settings.lnbits_running:
        funding_source = get_funding_source()
        if (
            settings.lnbits_watchdog
            and funding_source.__class__.__name__ != "VoidWallet"
        ):
            try:
                balance = await get_balance_delta()
                delta = balance.delta_msats
                logger.debug(f"Running watchdog task. current delta: {delta}")
                if delta + settings.lnbits_watchdog_delta <= 0:
                    logger.error(f"Switching to VoidWallet. current delta: {delta}")
                    await switch_to_voidwallet()
            except Exception as e:
                logger.error("Error in watchdog task", e)
        await asyncio.sleep(settings.lnbits_watchdog_interval * 60)


async def wait_for_paid_invoices(invoice_paid_queue: asyncio.Queue):
    """
    This worker dispatches events to all extensions and dispatches webhooks.
    """
    while settings.lnbits_running:
        payment = await invoice_paid_queue.get()
        logger.trace("received invoice paid event")
        # payment notification
        wallet = await get_wallet(payment.wallet_id)
        if wallet:
            await send_payment_notification(wallet, payment)
        # dispatch webhook
        if payment.webhook and not payment.webhook_status:
            await dispatch_webhook(payment)
        # dispatch push notification
        await send_payment_push_notification(payment)


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


async def wait_for_audit_data():
    """
    Waits for audit entries to be pushed to the queue.
    Then it inserts the entries into the DB.
    """
    while settings.lnbits_running:
        data: AuditEntry = await audit_queue.get()
        try:
            await create_audit_entry(data)
        except Exception as ex:
            logger.warning(ex)
            await asyncio.sleep(3)


async def purge_audit_data():
    """
    Remove audit entries which have passed their retention period.
    """
    while settings.lnbits_running:
        try:
            await delete_expired_audit_entries()
        except Exception as ex:
            logger.warning(ex)

        # clean every hour
        await asyncio.sleep(60 * 60)


async def collect_exchange_rates_data():
    """
    Collect exchange rates data. Used for monitoring only.
    """
    while settings.lnbits_running:
        currency = settings.lnbits_default_accounting_currency or "USD"
        max_history_size = settings.lnbits_exchange_history_size
        sleep_time = settings.lnbits_exchange_history_refresh_interval_seconds

        if sleep_time > 0:
            try:
                rates = await btc_rates(currency)
                if rates:
                    rates_values = [r[1] for r in rates]
                    lnbits_rate = sum(rates_values) / len(rates_values)
                    rates.append(("LNbits", lnbits_rate))
                settings.append_exchange_rate_datapoint(dict(rates), max_history_size)
            except Exception as ex:
                logger.warning(ex)
        else:
            sleep_time = 60
        await asyncio.sleep(sleep_time)
