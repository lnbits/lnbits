import asyncio

from lnbits.core.crud import create_audit_entry
from lnbits.core.crud.payments import get_payments_status_count
from lnbits.core.crud.users import get_accounts
from lnbits.core.crud.wallets import get_wallets_count
from lnbits.core.models.audit import AuditEntry
from lnbits.core.models.extensions import InstallableExtension
from lnbits.core.models.notifications import NotificationType
from lnbits.core.services.funding_source import get_balance_delta
from lnbits.core.services.notifications import (
    enqueue_admin_notification,
)
from lnbits.db import Filters
from lnbits.settings import settings
from lnbits.utils.exchange_rates import btc_rates

audit_queue: asyncio.Queue[AuditEntry] = asyncio.Queue()


async def process_next_audit_entry() -> None:
    """
    Waits for audit entries to be pushed to the queue.
    Then it inserts the entries into the DB.
    """
    data = await audit_queue.get()
    await create_audit_entry(data)


async def refresh_extension_cache() -> None:
    await InstallableExtension.get_installable_extensions(post_refresh_cache=True)


async def notify_server_status() -> None:
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
    enqueue_admin_notification(NotificationType.server_status, values)


async def collect_exchange_rates_data() -> None:
    """
    Collect exchange rates data. Used for monitoring only.
    """
    currency = settings.lnbits_default_accounting_currency or "USD"
    max_history_size = settings.lnbits_exchange_history_size
    rates = await btc_rates(currency)
    if rates:
        rates_values = [r[1] for r in rates]
        lnbits_rate = sum(rates_values) / len(rates_values)
        rates.append(("LNbits", lnbits_rate))
    settings.append_exchange_rate_datapoint(dict(rates), max_history_size)
