import asyncio
import json
from typing import Any

from fastapi import FastAPI
from loguru import logger

from lnbits.core.crud import (
    create_audit_entry,
    get_wallet,
)
from lnbits.core.crud.audit import delete_expired_audit_entries
from lnbits.core.crud.payments import get_payments_status_count
from lnbits.core.crud.users import get_accounts
from lnbits.core.crud.wallets import get_wallets_count
from lnbits.core.db import core_app_extra
from lnbits.core.models.audit import AuditEntry
from lnbits.core.models.extensions import InstallableExtension
from lnbits.core.models.notifications import NotificationType
from lnbits.core.services.funding_source import (
    check_balance_delta_changed,
    check_server_balance_against_node,
    get_balance_delta,
)
from lnbits.core.services.notifications import (
    enqueue_admin_notification,
    process_next_notification,
    send_payment_notification,
)
from lnbits.db import Filters
from lnbits.settings import settings
from lnbits.utils.cache import cache
from lnbits.utils.exchange_rates import btc_price_from_aggregator, btc_rates

audit_queue: asyncio.Queue[AuditEntry] = asyncio.Queue()


async def run_by_the_minute_tasks() -> None:
    minute_counter = 0
    while settings.lnbits_running:
        status_minutes = settings.lnbits_notification_server_status_hours * 60

        if settings.notification_balance_delta_threshold_sats > 0:
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
                await InstallableExtension.get_installable_extensions(
                    post_refresh_cache=True
                )
            except Exception as ex:
                logger.error(ex)

        minute_counter += 1
        await asyncio.sleep(60)


async def _notify_server_status() -> None:
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


async def wait_for_paid_invoices(invoice_paid_queue: asyncio.Queue) -> None:
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
        await core_app_extra.dispatch_extension_invoice_paid(payment)


async def dispatch_wasm_invoice_paid(app: FastAPI, payment: Any) -> None:
    extension_id = _payment_extension_id(payment)
    if not extension_id:
        return

    extensions = getattr(app.state, "lnbits_wasm_extensions", {})
    extension = extensions.get(extension_id)
    if not extension:
        return

    export_name = _wasm_invoice_paid_export(extension.config)
    if not export_name:
        return

    if not _is_wasm_event_export(extension, export_name):
        logger.warning(
            f"WASM extension '{extension.id}' declares invalid onInvoicePaid "
            f"export '{export_name}'."
        )
        return

    try:
        from lnbits.core.extensions.wasm import invoke_wasm_extension_export

        await invoke_wasm_extension_export(
            app,
            extension.id,
            export_name,
            _wasm_invoice_paid_payload(payment),
            context="event",
            owner_id=await _wasm_invoice_paid_owner_id(extension, payment),
        )
    except Exception as exc:
        logger.warning(
            f"WASM extension '{extension.id}' failed to handle paid invoice "
            f"'{payment.payment_hash}': {exc!s}"
        )


def _payment_extension_id(payment: Any) -> str | None:
    if isinstance(payment.extension, str) and payment.extension:
        return payment.extension

    extra = payment.extra or {}
    tag = extra.get("tag") or payment.tag
    return tag if isinstance(tag, str) and tag else None


async def _wasm_invoice_paid_owner_id(extension: Any, payment: Any) -> str | None:
    source_id = _payment_source_id(payment)
    source_table = _wasm_public_invoice_source_table(extension.config)
    if not source_id or not source_table:
        return None

    from lnbits.core.extensions.storage import storage_get_row_owner_id

    return await storage_get_row_owner_id(extension.id, source_table, source_id)


def _payment_source_id(payment: Any) -> str | None:
    extra = payment.extra or {}
    source_id = extra.get("source_id")
    return source_id if isinstance(source_id, str) and source_id else None


def _wasm_public_invoice_source_table(config: dict[str, Any]) -> str | None:
    permissions = config.get("permissions") or []
    for permission in permissions:
        if not isinstance(permission, dict):
            continue
        if permission.get("id") != "wallet.create_invoice_public":
            continue
        policy = permission.get("policy") or {}
        table = policy.get("table")
        return table if isinstance(table, str) and table else None
    return None


def _wasm_invoice_paid_export(config: dict[str, Any]) -> str | None:
    events = config.get("events") or {}
    export_name = events.get("onInvoicePaid")
    return export_name if isinstance(export_name, str) and export_name else None


def _is_wasm_event_export(extension: Any, export_name: str) -> bool:
    for export in extension.exports:
        if export.get("name") == export_name:
            return export.get("visibility") == "event"
    return False


def _wasm_invoice_paid_payload(payment: Any) -> dict[str, Any]:
    return {
        "checkingId": payment.checking_id,
        "paymentHash": payment.payment_hash,
        "walletId": payment.wallet_id,
        "amount": payment.amount,
        "fee": payment.fee,
        "bolt11": payment.bolt11,
        "memo": payment.memo,
        "pending": payment.pending,
        "status": payment.status,
        "tag": payment.tag,
        "extension": payment.extension,
        "extra": payment.extra or {},
        "payment": json.loads(payment.json()),
    }


async def wait_for_audit_data() -> None:
    """
    Waits for audit entries to be pushed to the queue.
    Then it inserts the entries into the DB.
    """
    while settings.lnbits_running:
        data = await audit_queue.get()
        try:
            await create_audit_entry(data)
        except Exception as ex:
            logger.warning(ex)
            await asyncio.sleep(3)


async def wait_notification_messages() -> None:

    while settings.lnbits_running:
        try:
            await process_next_notification()
        except Exception as ex:
            logger.warning("Payment notification error", ex)
            await asyncio.sleep(3)


async def purge_audit_data() -> None:
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


async def collect_exchange_rates_data() -> None:
    """
    Collect exchange rates data. Used for monitoring only.
    """
    while settings.lnbits_running:
        currency = settings.lnbits_default_accounting_currency or "USD"
        max_history_size = settings.lnbits_exchange_history_size
        sleep_time = settings.lnbits_exchange_history_refresh_interval_seconds

        if sleep_time > 0:
            try:
                if (
                    settings.lnbits_price_aggregator_enabled
                    and settings.lnbits_price_aggregator_url
                ):
                    price = await btc_price_from_aggregator(currency)
                    if price:
                        cache.set(
                            f"btc-price-{currency}",
                            price,
                            expiry=settings.lnbits_exchange_rate_cache_seconds,
                        )
                        settings.append_exchange_rate_datapoint(
                            {"Aggregator": price}, max_history_size
                        )
                else:
                    rates = await btc_rates(currency)
                    if rates:
                        rates_values = [r[1] for r in rates]
                        lnbits_rate = sum(rates_values) / len(rates_values)
                        rates.append(("LNbits", lnbits_rate))
                        cache.set(
                            f"btc-price-{currency}",
                            lnbits_rate,
                            expiry=settings.lnbits_exchange_rate_cache_seconds,
                        )
                    settings.append_exchange_rate_datapoint(
                        dict(rates), max_history_size
                    )
            except Exception as ex:
                logger.warning(ex)
        else:
            sleep_time = 60
        await asyncio.sleep(sleep_time)
