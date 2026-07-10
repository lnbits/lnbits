import json
from collections.abc import Iterable
from typing import Any

from loguru import logger

from lnbits.core.crud.extensions import get_installed_extension
from lnbits.core.db import core_app_extra
from lnbits.core.wasm_ext.storage.crud import storage_get_row_owner_id
from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export


async def dispatch_wasm_invoice_paid(payment: Any) -> None:
    extension_id = _payment_extension_id(payment)
    if not extension_id:
        return

    extension = core_app_extra.wasm_extension_registry.get(extension_id)
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
        owner_id = await _wasm_invoice_paid_owner_id(extension, payment)
        await invoke_wasm_extension_export(
            extension.id,
            export_name,
            _wasm_invoice_paid_payload(payment),
            context="event",
            owner_id=owner_id,
            trigger_type="event",
            event_type="invoice_paid",
            wallet_id=payment.wallet_id,
            payment_hash=payment.payment_hash,
            checking_id=payment.checking_id,
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
    source_tables = await _wasm_public_invoice_source_tables(extension.id)
    if not source_id or not source_tables:
        return None

    for source_table in source_tables:
        owner_id = await storage_get_row_owner_id(extension.id, source_table, source_id)
        if owner_id:
            return owner_id
    return None


def _payment_source_id(payment: Any) -> str | None:
    extra = payment.extra or {}
    source_id = extra.get("source_id")
    return source_id if isinstance(source_id, str) and source_id else None


async def _wasm_public_invoice_source_tables(extension_id: str) -> list[str]:
    installed_extension = await get_installed_extension(extension_id)
    if not installed_extension:
        return []
    return _wasm_public_invoice_source_tables_from_permissions(
        installed_extension.permissions
    )


def _wasm_public_invoice_source_tables_from_permissions(
    permissions: Iterable[Any],
) -> list[str]:
    for permission in permissions:
        permission_id = (
            permission.get("id")
            if isinstance(permission, dict)
            else getattr(permission, "id", None)
        )
        if permission_id != "wallet.create_invoice_public":
            continue
        policies = (
            permission.get("policies")
            if isinstance(permission, dict)
            else getattr(permission, "policies", None)
        )
        if not isinstance(policies, list):
            return []
        return [
            source_policy["table"]
            for source_policy in policies
            if isinstance(source_policy, dict)
            and isinstance(source_policy.get("table"), str)
            and source_policy["table"]
        ]
    return []


def _wasm_invoice_paid_export(config: Any) -> str | None:
    return config.events.on_invoice_paid


def _is_wasm_event_export(extension: Any, export_name: str) -> bool:
    for export in extension.exports:
        if export.name == export_name:
            return export.visibility == "event"
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
