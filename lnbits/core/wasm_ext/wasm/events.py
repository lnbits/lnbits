import json
from collections.abc import Iterable
from typing import Any

from loguru import logger

from lnbits.core.crud.extensions import get_installed_extension, get_user_extensions
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.db import core_app_extra
from lnbits.core.models.extensions import ExtensionWalletPaymentsWatchGrant
from lnbits.core.wasm_ext.storage.crud import storage_get_row_owner_id
from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export
from lnbits.helpers import sha256s

WALLET_PAYMENTS_WATCH_PERMISSION = "wallet.payments.watch"


async def dispatch_wasm_invoice_paid(payment: Any) -> None:
    targets: dict[str, tuple[Any, str | None]] = {}
    extension_id = _payment_extension_id(payment)
    if extension_id:
        extension = core_app_extra.wasm_extension_registry.get(extension_id)
        if extension:
            targets[extension_id] = (
                extension,
                await _wasm_invoice_paid_owner_id(extension, payment),
            )

    wallet = await _payment_wallet(payment)
    if wallet:
        wallet_owner_id = sha256s(wallet.user)
        for watch_extension_id in await _wallet_watch_extension_ids(
            wallet.user, wallet.id
        ):
            extension = core_app_extra.wasm_extension_registry.get(watch_extension_id)
            if not extension:
                continue
            if watch_extension_id in targets:
                existing_extension, existing_owner_id = targets[watch_extension_id]
                targets[watch_extension_id] = (
                    existing_extension,
                    existing_owner_id or wallet_owner_id,
                )
                continue
            targets[watch_extension_id] = (extension, wallet_owner_id)

    for extension, owner_id in targets.values():
        await _dispatch_wasm_invoice_paid_to_extension(extension, payment, owner_id)


async def _dispatch_wasm_invoice_paid_to_extension(
    extension: Any, payment: Any, owner_id: str | None
) -> None:
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


async def _payment_wallet(payment: Any) -> Any | None:
    wallet_id = getattr(payment, "wallet_id", None)
    if not isinstance(wallet_id, str) or not wallet_id:
        return None
    try:
        return await get_wallet(wallet_id)
    except Exception as exc:
        logger.warning(f"Could not fetch wallet '{wallet_id}' for WASM event: {exc!s}")
        return None


async def _wallet_watch_extension_ids(user_id: str, wallet_id: str) -> list[str]:
    try:
        user_extensions = await get_user_extensions(user_id)
    except Exception as exc:
        logger.warning(
            f"Could not fetch extensions for wallet payment watch user "
            f"'{user_id}': {exc!s}"
        )
        return []
    extension_ids: list[str] = []

    for user_extension in user_extensions:
        if not user_extension.active:
            continue
        if not _has_wallet_watch_grant(user_extension, wallet_id):
            continue
        if not core_app_extra.wasm_extension_registry.get(user_extension.extension):
            continue
        try:
            installed_extension = await get_installed_extension(
                user_extension.extension
            )
        except Exception as exc:
            logger.warning(
                f"Could not fetch installed extension '{user_extension.extension}' "
                f"for wallet payment watch: {exc!s}"
            )
            continue
        if not installed_extension or not installed_extension.active:
            continue
        if not _extension_has_permission(
            installed_extension, WALLET_PAYMENTS_WATCH_PERMISSION
        ):
            continue
        extension_ids.append(user_extension.extension)

    return extension_ids


def _has_wallet_watch_grant(user_extension: Any, wallet_id: str) -> bool:
    permissions = user_extension.permissions or {}
    grants = permissions.get(WALLET_PAYMENTS_WATCH_PERMISSION)
    if not isinstance(grants, list):
        return False

    for grant_data in grants:
        if not isinstance(grant_data, dict):
            continue
        try:
            grant = ExtensionWalletPaymentsWatchGrant.parse_obj(grant_data)
        except ValueError:
            continue
        if grant.enabled and grant.wallet_id == wallet_id:
            return True
    return False


def _extension_has_permission(extension: Any, permission_id: str) -> bool:
    return any(
        (
            permission.get("id")
            if isinstance(permission, dict)
            else getattr(permission, "id", None)
        )
        == permission_id
        for permission in (extension.permissions or [])
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
