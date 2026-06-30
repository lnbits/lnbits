import json
from typing import Any

from loguru import logger

from lnbits.core.db import core_app_extra


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
        from lnbits.core.extensions.wasm import invoke_wasm_extension_export

        await invoke_wasm_extension_export(
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
