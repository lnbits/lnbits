from __future__ import annotations

from typing import Any, NoReturn

from bolt11 import decode as bolt11_decode
from loguru import logger

from lnbits.core.crud.extensions import get_user_extension
from lnbits.core.crud.payments import check_internal
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models.extensions import (
    ExtensionBackgroundPaymentDestinationPolicy,
    ExtensionBackgroundPaymentGrant,
)
from lnbits.core.models.wallets import Wallet

WALLET_PAY_INVOICE_BACKGROUND_PERMISSION = "wallet.pay_invoice_background"


async def background_payment_extra(
    *,
    extension_id: str,
    wallet: Wallet,
    payment_request: str,
    amount_msat: int,
) -> dict[str, Any]:
    grant = await _background_payment_grant(extension_id, wallet, amount_msat)
    await _check_destination_policy(extension_id, wallet, grant, payment_request)

    return {
        "tag": extension_id,
        "extension": extension_id,
        "background_payment": True,
        "background_permission": WALLET_PAY_INVOICE_BACKGROUND_PERMISSION,
        "background_wallet_id": wallet.source_wallet_id,
        "background_destination_policy": grant.destination_policy.value,
    }


def invoice_amount_msat(payment_request: str) -> int:
    invoice = bolt11_decode(payment_request)
    amount_msat = int(invoice.amount_msat or 0)
    if amount_msat <= 0:
        raise PermissionError("Background payments require an invoice amount.")
    return amount_msat


async def _background_payment_grant(
    extension_id: str,
    wallet: Wallet,
    amount_msat: int,
) -> ExtensionBackgroundPaymentGrant:
    if wallet.is_lightning_shared_wallet:
        _deny(extension_id, wallet, amount_msat, "shared wallet")
    if not wallet.can_send_payments:
        _deny(extension_id, wallet, amount_msat, "wallet cannot send payments")

    user_extension = await get_user_extension(wallet.user, extension_id)
    if not user_extension or not user_extension.active:
        _deny(extension_id, wallet, amount_msat, "extension disabled for user")

    permissions = user_extension.permissions or {}
    grants = permissions.get(WALLET_PAY_INVOICE_BACKGROUND_PERMISSION)
    if not isinstance(grants, list):
        _deny(extension_id, wallet, amount_msat, "missing background payment grant")

    grant = _find_wallet_grant(grants, wallet.id)
    if not grant:
        _deny(extension_id, wallet, amount_msat, "missing wallet background grant")
    if not grant.enabled:
        _deny(extension_id, wallet, amount_msat, "background grant disabled")
    if amount_msat > grant.max_amount * 1000:
        _deny(extension_id, wallet, amount_msat, "payment exceeds max amount")
    return grant


def _find_wallet_grant(
    grants: list[Any], wallet_id: str
) -> ExtensionBackgroundPaymentGrant | None:
    for grant_data in grants:
        if not isinstance(grant_data, dict):
            continue
        try:
            grant = ExtensionBackgroundPaymentGrant.parse_obj(grant_data)
        except ValueError:
            continue
        if grant.wallet_id == wallet_id:
            return grant
    return None


async def _check_destination_policy(
    extension_id: str,
    wallet: Wallet,
    grant: ExtensionBackgroundPaymentGrant,
    payment_request: str,
) -> None:
    if (
        grant.destination_policy
        == ExtensionBackgroundPaymentDestinationPolicy.EXTERNAL_ALLOWED
    ):
        return

    payment_hash = bolt11_decode(payment_request).payment_hash
    internal_payment = await check_internal(payment_hash)
    if not internal_payment:
        _deny(extension_id, wallet, 0, "external destination not allowed")

    destination_wallet = await get_wallet(internal_payment.wallet_id)
    if not destination_wallet or destination_wallet.user != wallet.user:
        _deny(extension_id, wallet, 0, "destination wallet is not owned by user")


def _deny(extension_id: str, wallet: Wallet, amount_msat: int, reason: str) -> NoReturn:
    logger.warning(
        "WASM extension '{}' denied background payment from wallet '{}', "
        "user '{}', amount_msat '{}': {}.",
        extension_id,
        wallet.id,
        wallet.user,
        amount_msat,
        reason,
    )
    raise PermissionError(reason)
