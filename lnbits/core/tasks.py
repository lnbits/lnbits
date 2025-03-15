import asyncio
import traceback
from typing import Callable, Coroutine

from loguru import logger

from lnbits.core.crud import (
    create_audit_entry,
    get_wallet,
)
from lnbits.core.crud.audit import delete_expired_audit_entries
from lnbits.core.crud.payments import get_payments_status_count
from lnbits.core.crud.users import get_accounts
from lnbits.core.crud.wallets import get_wallets_count
from lnbits.core.models import AuditEntry
from lnbits.core.models.extensions import InstallableExtension
from lnbits.core.models.notifications import NotificationType
from lnbits.core.services.funding_source import (
    check_balance_delta_changed,
    check_server_balance_against_node,
    get_balance_delta,
)
from lnbits.core.services.notifications import (
    enqueue_notification,
    process_next_notification,
    send_payment_notification,
)
from lnbits.db import Filters
from lnbits.settings import settings
from lnbits.tasks import create_unique_task
from lnbits.utils.exchange_rates import btc_rates

audit_queue: asyncio.Queue = asyncio.Queue()


async def run_by_the_minute_tasks():
    minute_counter = 0
    while settings.lnbits_running:
        status_minutes = settings.lnbits_notification_server_status_hours * 60

        if settings.notification_balance_delta_changed:
            try:
                # runs by default every minute, the delta should not change that often
                await check_balance_delta_changed()
            except Exception as ex:
                logger.error(ex)

        if minute_counter % settings.lnbits_watchdog_interval_minutes == 0:
            try:
                await check_server_balance_against_node()
            except Exception as ex:
                logger.error(ex)

        if minute_counter % status_minutes == 0:
            try:
                await _notify_server_status()
            except Exception as ex:
                logger.error(ex)

        if minute_counter % 60 == 0:
            try:
                # initialize the list of all extensions
                await InstallableExtension.get_installable_extensions()
            except Exception as ex:
                logger.error(ex)

        minute_counter += 1
        await asyncio.sleep(60)


async def _notify_server_status():
    accounts = await get_accounts(filters=Filters(limit=0))
    wallets_count = await get_wallets_count()
    payments = await get_payments_status_count()

    status = await get_balance_delta()
    values = {
        "up_time": settings.lnbits_server_up_time,
        "accounts_count": accounts.total,
        "wallets_count": wallets_count,
        "in_payments_count": payments.incoming,
        "out_payments_count": payments.outgoing,
        "pending_payments_count": payments.pending,
        "failed_payments_count": payments.failed,
        "delta_sats": status.delta_sats,
        "lnbits_balance_sats": status.lnbits_balance_sats,
        "node_balance_sats": status.node_balance_sats,
    }
    enqueue_notification(NotificationType.server_status, values)


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


async def wait_notification_messages():

    while settings.lnbits_running:
        try:
            await process_next_notification()
        except Exception as ex:
            logger.log("error", ex)
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


def _create_unique_task(name: str, func: Callable):
    async def _to_coro(func: Callable[[], Coroutine]) -> Coroutine:
        return await func()

    try:
        create_unique_task(name, _to_coro(func))
    except Exception as e:
        logger.error(f"Error in {name} task", e)
        logger.error(traceback.format_exc())
