import json
import sys
import traceback
from http import HTTPStatus

import httpx
from bolt11 import decode as bolt11_decode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from loguru import logger

from lnbits.core.crud.extensions import get_user_extensions
from lnbits.core.crud.wallets import get_wallet, get_wallets_ids
from lnbits.core.db import db
from lnbits.core.models import (
    SimpleStatus,
)
from lnbits.core.models.extensions import (
    CreateExtension,
    CreateExtensionReview,
    Extension,
    ExtensionBackgroundPaymentDestinationPolicy,
    ExtensionBackgroundPaymentGrant,
    ExtensionBackgroundPaymentGrantRequest,
    ExtensionConfig,
    ExtensionMeta,
    ExtensionPermissionCheckRequest,
    ExtensionPermissionCheckResponse,
    ExtensionPermissionCheckResult,
    ExtensionPermissionsResponse,
    ExtensionPermissionsUpdate,
    ExtensionRelease,
    ExtensionReview,
    ExtensionReviewPaymentRequest,
    ExtensionReviewsStatus,
    ExtensionWalletPaymentsWatchGrant,
    ExtensionWalletPaymentsWatchGrantRequest,
    InstallableExtension,
    PayToEnableInfo,
    ReleasePaymentInfo,
    UserExtension,
    UserExtensionInfo,
    WasmInvocation,
    WasmInvocationStats,
    WasmRuntimeLimitsInfo,
    WasmRuntimeLimitsUpdate,
    wasm_extension_icon_url,
)
from lnbits.core.models.users import Account, AccountId
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.core.services.extensions import (
    activate_extension,
    deactivate_extension,
    get_current_wasm_invocations,
    get_valid_extension,
    get_valid_extensions,
    get_wasm_invocation_history,
    get_wasm_invocation_summary,
    install_extension,
    resolve_wasm_runtime_limits,
    stop_wasm_invocation,
    uninstall_extension,
    update_wasm_extension_runtime_limits,
    validate_wasm_runtime_limit_overrides,
)
from lnbits.core.wasm_ext.api.permissions import (
    validate_extension_permissions,
    validate_wasm_extension_permissions,
)
from lnbits.db import Page
from lnbits.decorators import (
    check_account_exists,
    check_account_id_exists,
    check_admin,
)
from lnbits.settings import settings

from ..crud import (
    create_user_extension,
    delete_dbversion,
    drop_extension_db,
    get_db_version,
    get_db_versions,
    get_installed_extension,
    get_installed_extensions,
    get_user_extension,
    update_installed_extension,
    update_user_extension,
)

extension_router = APIRouter(
    tags=["Extension Managment"],
    prefix="/api/v1/extension",
)

WALLET_PAY_INVOICE_BACKGROUND_PERMISSION = "wallet.pay_invoice_background"
WALLET_PAYMENTS_WATCH_PERMISSION = "wallet.payments.watch"


@extension_router.post("", dependencies=[Depends(check_admin)])
async def api_install_extension(data: CreateExtension):
    release = await InstallableExtension.get_extension_release(
        data.ext_id, data.source_repo, data.archive, data.version
    )
    if not release:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Release not found")

    if not release.is_version_compatible:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Incompatible extension version.")

    release.payment_hash = data.payment_hash
    ext_meta = ExtensionMeta(installed_release=release)
    ext_info = InstallableExtension(
        id=data.ext_id,
        name=data.ext_id,
        version=data.version,
        meta=ext_meta,
        icon=release.icon,
    )

    try:
        extension = await install_extension(
            ext_info,
            granted_permissions=data.permissions,
            allow_admin_policy_overrides=True,
        )

    except Exception as exc:
        logger.warning(exc)
        etype, _, tb = sys.exc_info()
        traceback.print_exception(etype, exc, tb)
        try:
            archive_config = ext_info.load_archive_config()
        except ValueError:
            archive_config = {}
        if archive_config.get("extension_type") == "wasm":
            ext_info.clean_wasm_extension_files()
        else:
            ext_info.clean_extension_files()
        detail = (
            str(exc)
            if isinstance(exc, (AssertionError, ValueError))
            else f"Failed to install extension '{ext_info.id}'."
            f"({ext_info.installed_version})."
        )
        raise HTTPException(
            status_code=(
                HTTPStatus.BAD_REQUEST
                if isinstance(exc, (AssertionError, ValueError))
                else HTTPStatus.INTERNAL_SERVER_ERROR
            ),
            detail=detail,
        ) from exc

    try:
        await activate_extension(extension)
        return extension
    except Exception as exc:
        logger.warning(exc)
        await deactivate_extension(extension.code)
        detail = (
            str(exc)
            if isinstance(exc, AssertionError)
            else f"Extension `{extension.code}` installed, but activation failed."
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc


@extension_router.get(
    "/wasm/invocations/current",
    dependencies=[Depends(check_admin)],
)
async def api_get_current_wasm_invocations(
    extension_id: str | None = None,
) -> list[WasmInvocation]:
    return get_current_wasm_invocations(extension_id=extension_id)


@extension_router.get(
    "/wasm/invocations",
    dependencies=[Depends(check_admin)],
)
async def api_get_wasm_invocations(
    extension_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[WasmInvocation]:
    return await get_wasm_invocation_history(
        extension_id=extension_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@extension_router.get(
    "/wasm/invocations/stats",
    dependencies=[Depends(check_admin)],
)
async def api_get_wasm_invocation_stats(
    extension_id: str | None = None,
    hours: int = 24,
) -> WasmInvocationStats:
    return await get_wasm_invocation_summary(extension_id=extension_id, hours=hours)


@extension_router.post(
    "/wasm/invocations/{invocation_id}/stop",
    dependencies=[Depends(check_admin)],
)
async def api_stop_wasm_invocation(invocation_id: str) -> SimpleStatus:
    await stop_wasm_invocation(invocation_id, reason="Stopped by admin.")
    return SimpleStatus(success=True, message="WASM invocation stop requested.")


@extension_router.get(
    "/wasm/runtime-limits/extensions",
    dependencies=[Depends(check_admin)],
)
async def api_get_wasm_runtime_limit_extensions() -> list[WasmRuntimeLimitsInfo]:
    installed_extensions = await get_installed_extensions()
    return [
        WasmRuntimeLimitsInfo(
            id=extension.id,
            name=extension.name,
            active=extension.active,
            wasm_runtime_limits=validate_wasm_runtime_limit_overrides(
                extension.wasm_runtime_limits,
                strict=False,
            ),
            effective_wasm_runtime_limits=resolve_wasm_runtime_limits(extension),
        )
        for extension in installed_extensions
        if extension.is_wasm
    ]


@extension_router.put(
    "/wasm/runtime-limits/{ext_id}",
    dependencies=[Depends(check_admin)],
)
async def api_update_wasm_runtime_limits(
    ext_id: str,
    data: WasmRuntimeLimitsUpdate,
) -> WasmRuntimeLimitsInfo:
    try:
        wasm_runtime_limits = await update_wasm_extension_runtime_limits(
            ext_id, data.limits
        )
        extension = await get_installed_extension(ext_id)
        if not extension:
            raise ValueError(f"Extension '{ext_id}' is not installed.")
        extension.wasm_runtime_limits = wasm_runtime_limits
        return WasmRuntimeLimitsInfo(
            id=extension.id,
            name=extension.name,
            active=extension.active,
            wasm_runtime_limits=wasm_runtime_limits,
            effective_wasm_runtime_limits=resolve_wasm_runtime_limits(extension),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(exc),
        ) from exc


@extension_router.get("/{ext_id}/details")
async def api_extension_details(
    ext_id: str,
    details_link: str,
):
    all_releases = await InstallableExtension.get_extension_releases(ext_id)

    release = next((r for r in all_releases if r.details_link == details_link), None)
    if not release:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Release not found"
        )

    release_details = await ExtensionRelease.fetch_release_details(details_link)
    if not release_details:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Cannot fetch details for release",
        )
    release_details["icon"] = release.icon
    release_details["repo"] = release.repo
    return release_details


@extension_router.put("/{ext_id}/sell")
async def api_update_pay_to_enable(
    ext_id: str,
    data: PayToEnableInfo,
    account: Account = Depends(check_admin),
) -> SimpleStatus:
    user_wallet_ids = await get_wallets_ids(account.id, deleted=False)
    if data.wallet not in user_wallet_ids:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Wallet does not belong to this admin user."
        )
    extension = await get_installed_extension(ext_id)
    if not extension:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' not found.")
    if extension.meta:
        extension.meta.pay_to_enable = data
    else:
        extension.meta = ExtensionMeta(pay_to_enable=data)
    await update_installed_extension(extension)
    return SimpleStatus(
        success=True, message=f"Payment info updated for '{ext_id}' extension."
    )


@extension_router.put("/{ext_id}/enable")
async def api_enable_extension(
    ext_id: str, account_id: AccountId = Depends(check_account_id_exists)
) -> SimpleStatus:
    if ext_id not in [e.code for e in await get_valid_extensions()]:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' doesn't exist."
        )

    logger.info(f"Enabling extension: {ext_id}.")
    ext = await get_installed_extension(ext_id)
    if not ext:
        raise ValueError(f"Extension '{ext_id}' is not installed.")
    if not ext.active:
        raise ValueError(f"Extension '{ext_id}' is not activated.")

    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext:
        user_ext = UserExtension(user=account_id.id, extension=ext_id, active=False)
        await create_user_extension(user_ext)

    if account_id.is_admin_id or not ext.requires_payment:
        user_ext.active = True
        await update_user_extension(user_ext)
        return SimpleStatus(success=True, message=f"Extension '{ext_id}' enabled.")

    if not (user_ext.extra and user_ext.extra.payment_hash_to_enable):
        raise HTTPException(
            HTTPStatus.PAYMENT_REQUIRED, f"Extension '{ext_id}' requires payment."
        )

    if user_ext.is_paid:
        user_ext.active = True
        await update_user_extension(user_ext)
        return SimpleStatus(success=True, message=f"Paid extension '{ext_id}' enabled.")

    if not ext.meta or not ext.meta.pay_to_enable or not ext.meta.pay_to_enable.wallet:
        raise ValueError(f"Extension '{ext_id}' is missing payment wallet.")

    payment_status = await check_transaction_status(
        wallet_id=ext.meta.pay_to_enable.wallet,
        payment_hash=user_ext.extra.payment_hash_to_enable,
    )

    if not payment_status.paid:
        raise HTTPException(
            HTTPStatus.PAYMENT_REQUIRED,
            f"Invoice generated but not paid for enabeling extension '{ext_id}'.",
        )

    user_ext.active = True
    user_ext.extra.paid_to_enable = True
    await update_user_extension(user_ext)
    return SimpleStatus(success=True, message=f"Paid extension '{ext_id}' enabled.")


@extension_router.put("/{ext_id}/disable")
async def api_disable_extension(
    ext_id: str, account_id: AccountId = Depends(check_account_id_exists)
) -> SimpleStatus:
    if ext_id not in [e.code for e in await get_valid_extensions()]:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, f"Extension '{ext_id}' doesn't exist."
        )
    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext or not user_ext.active:
        return SimpleStatus(
            success=True, message=f"Extension '{ext_id}' already disabled."
        )
    logger.info(f"Disabling extension: {ext_id}.")
    user_ext.active = False
    await update_user_extension(user_ext)
    return SimpleStatus(success=True, message=f"Extension '{ext_id}' disabled.")


@extension_router.post("/{ext_id}/permissions/background-payment")
async def api_grant_background_payment_permission(
    ext_id: str,
    data: ExtensionBackgroundPaymentGrantRequest,
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    installed_ext = await get_installed_extension(ext_id)
    if not installed_ext or not installed_ext.active:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' is not active."
        )

    installed_permission_ids = {
        permission.id for permission in installed_ext.permissions or []
    }
    if WALLET_PAY_INVOICE_BACKGROUND_PERMISSION not in installed_permission_ids:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            f"Extension '{ext_id}' cannot request background payments.",
        )

    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext or not user_ext.active:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            f"Extension '{ext_id}' is not enabled for this user.",
        )

    wallet = await get_wallet(data.wallet_id)
    if not wallet or wallet.user != account_id.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your wallet.")
    if wallet.is_lightning_shared_wallet:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "Background payments are not allowed from shared wallets.",
        )
    if not wallet.can_send_payments:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "This wallet cannot send payments.",
        )

    permissions = user_ext.permissions or {}
    grant = data.to_grant(
        _user_permission_grant_id_for_wallet(
            permissions,
            WALLET_PAY_INVOICE_BACKGROUND_PERMISSION,
            data.wallet_id,
        )
    )
    background_grants = [
        existing
        for existing in permissions.get(WALLET_PAY_INVOICE_BACKGROUND_PERMISSION, [])
        if isinstance(existing, dict) and existing.get("wallet_id") != grant.wallet_id
    ]
    background_grants.append(json.loads(grant.json()))
    permissions[WALLET_PAY_INVOICE_BACKGROUND_PERMISSION] = background_grants
    user_ext.permissions = permissions
    await update_user_extension(user_ext)
    return {"permission": WALLET_PAY_INVOICE_BACKGROUND_PERMISSION, "grant": grant}


@extension_router.post("/{ext_id}/permissions/wallet-payments-watch")
async def api_grant_wallet_payments_watch_permission(
    ext_id: str,
    data: ExtensionWalletPaymentsWatchGrantRequest,
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    installed_ext = await get_installed_extension(ext_id)
    if not installed_ext or not installed_ext.active:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' is not active."
        )

    installed_permission_ids = {
        permission.id for permission in installed_ext.permissions or []
    }
    if WALLET_PAYMENTS_WATCH_PERMISSION not in installed_permission_ids:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            f"Extension '{ext_id}' cannot request wallet payment watch access.",
        )

    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext or not user_ext.active:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            f"Extension '{ext_id}' is not enabled for this user.",
        )

    wallet = await get_wallet(data.wallet_id)
    if not wallet or wallet.user != account_id.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your wallet.")

    permissions = user_ext.permissions or {}
    grant = data.to_grant(
        _user_permission_grant_id_for_wallet(
            permissions,
            WALLET_PAYMENTS_WATCH_PERMISSION,
            data.wallet_id,
        )
    )
    watch_grants = [
        existing
        for existing in permissions.get(WALLET_PAYMENTS_WATCH_PERMISSION, [])
        if isinstance(existing, dict) and existing.get("wallet_id") != grant.wallet_id
    ]
    watch_grants.append(json.loads(grant.json()))
    permissions[WALLET_PAYMENTS_WATCH_PERMISSION] = watch_grants
    user_ext.permissions = permissions
    await update_user_extension(user_ext)
    return {"permission": WALLET_PAYMENTS_WATCH_PERMISSION, "grant": grant}


@extension_router.get("/{ext_id}/permissions")
async def api_get_extension_permissions(
    ext_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> ExtensionPermissionsResponse:
    installed_ext = await _require_active_wasm_extension(ext_id)
    extension_permissions = validate_extension_permissions(
        installed_ext.id, installed_ext.permissions, strict=False
    )
    user_ext = await get_user_extension(account_id.id, ext_id)
    return ExtensionPermissionsResponse(
        extension_permissions=extension_permissions,
        user_permissions=_safe_user_extension_permissions(
            user_ext.permissions if user_ext else {}
        ),
    )


@extension_router.put("/{ext_id}/permissions", dependencies=[Depends(check_admin)])
async def api_update_extension_permissions(
    ext_id: str,
    data: ExtensionPermissionsUpdate,
) -> ExtensionPermissionsResponse:
    installed_ext = await get_installed_extension(ext_id)
    if not installed_ext:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' is not installed."
        )
    if not installed_ext.is_wasm:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, f"Extension '{ext_id}' is not a WASM extension."
        )

    try:
        extension_config = _load_installed_extension_config(installed_ext)
        installed_ext.permissions = validate_wasm_extension_permissions(
            installed_ext,
            data.permissions,
            extension_config,
            allow_admin_policy_overrides=True,
        )
        await update_installed_extension(installed_ext)
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ExtensionPermissionsResponse(
        extension_permissions=validate_extension_permissions(
            installed_ext.id, installed_ext.permissions, strict=False
        )
    )


@extension_router.delete("/{ext_id}/permissions/user/{grant_id}")
async def api_delete_user_extension_permission(
    ext_id: str,
    grant_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    await _require_active_wasm_extension(ext_id)

    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext:
        return SimpleStatus(success=True, message="Permission grant removed.")

    user_ext.permissions = _remove_user_permission_grant(
        user_ext.permissions or {}, grant_id
    )
    await update_user_extension(user_ext)
    return SimpleStatus(success=True, message="Permission grant removed.")


@extension_router.post("/{ext_id}/permissions/check")
async def api_check_extension_permissions(
    ext_id: str,
    data: ExtensionPermissionCheckRequest,
    account_id: AccountId = Depends(check_account_id_exists),
) -> ExtensionPermissionCheckResponse:
    installed_ext = await get_installed_extension(ext_id)
    if not installed_ext or not installed_ext.active:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' is not active."
        )

    installed_permission_ids = {
        permission.id for permission in installed_ext.permissions or []
    }

    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext or not user_ext.active:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            f"Extension '{ext_id}' is not enabled for this user.",
        )

    results: list[ExtensionPermissionCheckResult] = []
    for permission in data.permissions:
        if permission.id not in installed_permission_ids:
            raise HTTPException(
                HTTPStatus.FORBIDDEN,
                f"Extension '{ext_id}' cannot request '{permission.id}'.",
            )
        if permission.id == WALLET_PAY_INVOICE_BACKGROUND_PERMISSION:
            results.append(
                await _check_background_payment_permission(
                    account_id.id,
                    user_ext.permissions or {},
                    permission.grant,
                )
            )
            continue
        if permission.id == WALLET_PAYMENTS_WATCH_PERMISSION:
            results.append(
                await _check_wallet_payments_watch_permission(
                    account_id.id,
                    user_ext.permissions or {},
                    permission.grant,
                )
            )
            continue
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            f"Unsupported permission check '{permission.id}'.",
        )

    return ExtensionPermissionCheckResponse(permissions=results)


@extension_router.put("/{ext_id}/activate", dependencies=[Depends(check_admin)])
async def api_activate_extension(ext_id: str) -> SimpleStatus:
    try:
        logger.info(f"Activating extension: '{ext_id}'.")

        ext = await get_valid_extension(ext_id)
        if not ext:
            raise ValueError(f"Extension '{ext_id}' doesn't exist.")

        await activate_extension(ext)
        return SimpleStatus(success=True, message=f"Extension '{ext_id}' activated.")
    except Exception as exc:
        logger.warning(exc)
        await deactivate_extension(ext_id)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=(f"Failed to activate '{ext_id}'."),
        ) from exc


@extension_router.put("/{ext_id}/deactivate", dependencies=[Depends(check_admin)])
async def api_deactivate_extension(ext_id: str) -> SimpleStatus:
    try:
        logger.info(f"Deactivating extension: '{ext_id}'.")

        ext = await get_valid_extension(ext_id)
        if not ext:
            raise ValueError(f"Extension '{ext_id}' doesn't exist.")

        await deactivate_extension(ext_id)
        return SimpleStatus(success=True, message=f"Extension '{ext_id}' deactivated.")
    except Exception as exc:
        logger.warning(exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=(f"Failed to deactivate '{ext_id}'."),
        ) from exc


@extension_router.delete("/{ext_id}", dependencies=[Depends(check_admin)])
async def api_uninstall_extension(ext_id: str) -> SimpleStatus:
    extension = await get_installed_extension(ext_id)
    if not extension:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Unknown extension id: {ext_id}",
        )

    installed_extensions = await get_installed_extensions()
    # check that other extensions do not depend on this one
    for valid_ext_id in [ext.code for ext in await get_valid_extensions()]:
        installed_ext = next(
            (ext for ext in installed_extensions if ext.id == valid_ext_id), None
        )
        if (
            installed_ext
            and installed_ext.meta
            and ext_id in installed_ext.meta.dependencies
        ):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"Cannot uninstall. Extension '{installed_ext.name}' "
                    "depends on this one."
                ),
            )

    try:
        await uninstall_extension(ext_id)

        logger.success(f"Extension '{ext_id}' uninstalled.")
        return SimpleStatus(success=True, message=f"Extension '{ext_id}' uninstalled.")
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@extension_router.get("/{ext_id}/releases", dependencies=[Depends(check_admin)])
async def get_extension_releases(ext_id: str) -> list[ExtensionRelease]:
    try:
        extension_releases: list[ExtensionRelease] = (
            await InstallableExtension.get_extension_releases(ext_id)
        )
        for release in extension_releases:
            release.permissions = validate_extension_permissions(
                ext_id, release.permissions
            )

        installed_ext = await get_installed_extension(ext_id)
        if not installed_ext:
            return extension_releases

        for release in extension_releases:
            payment_info = installed_ext.find_existing_payment(release.pay_link)
            if payment_info:
                release.paid_sats = payment_info.amount

        return extension_releases

    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@extension_router.put("/{ext_id}/invoice/install", dependencies=[Depends(check_admin)])
async def get_pay_to_install_invoice(
    ext_id: str, data: CreateExtension
) -> ReleasePaymentInfo:
    if ext_id != data.ext_id:
        raise ValueError(
            f"Wrong extension id. Expected {ext_id}, but got {data.ext_id}"
        )
    if not data.cost_sats:
        raise ValueError("A non-zero amount must be specified.")
    release = await InstallableExtension.get_extension_release(
        data.ext_id, data.source_repo, data.archive, data.version
    )
    if not release:
        raise ValueError("Release not found.")
    if not release.pay_link:
        raise ValueError("Pay link not found for release.")

    payment_info = await release.fetch_release_payment_info(data.cost_sats)

    if not (payment_info and payment_info.payment_request):
        raise ValueError("Cannot request invoice.")
    invoice = bolt11_decode(payment_info.payment_request)

    if invoice.amount_msat is None:
        raise ValueError("Invoic amount is missing.")
    invoice_amount = int(invoice.amount_msat / 1000)
    if invoice_amount != data.cost_sats:
        raise ValueError(f"Wrong invoice amount: {invoice_amount}.")
    if payment_info.payment_hash != invoice.payment_hash:
        raise ValueError("Wrong invoice payment hash.")

    return payment_info


@extension_router.put("/{ext_id}/invoice/enable")
async def get_pay_to_enable_invoice(
    ext_id: str,
    data: PayToEnableInfo,
    account_id: AccountId = Depends(check_account_id_exists),
):
    if not data.amount or data.amount <= 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Amount must be greater than 0."
        )

    ext = await get_installed_extension(ext_id)
    if not ext:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Extension '{ext_id}' not found."
        )

    if not ext.meta or not ext.meta.pay_to_enable:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Payment info not found for extension '{ext_id}'.",
        )

    if not ext.meta.pay_to_enable.required:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Payment not required for extension '{ext_id}'.",
        )

    if not ext.meta.pay_to_enable.wallet or not ext.meta.pay_to_enable.amount:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Payment wallet or amount missing for extension '{ext_id}'.",
        )

    if data.amount < ext.meta.pay_to_enable.amount:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Amount {data.amount} sats is less than required "
                f"{ext.meta.pay_to_enable.amount} sats."
            ),
        )

    payment = await create_invoice(
        wallet_id=ext.meta.pay_to_enable.wallet,
        amount=data.amount,
        memo=f"Enable '{ext.name}' extension.",
    )

    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext:
        user_ext = UserExtension(user=account_id.id, extension=ext_id, active=False)
        await create_user_extension(user_ext)
    user_ext_info = user_ext.extra if user_ext.extra else UserExtensionInfo()
    user_ext_info.payment_hash_to_enable = payment.payment_hash
    user_ext.extra = user_ext_info
    await update_user_extension(user_ext)
    return {"payment_hash": payment.payment_hash, "payment_request": payment.bolt11}


@extension_router.get(
    "/release/{org}/{repo}/{tag_name}",
    dependencies=[Depends(check_account_exists)],
)
async def get_extension_release(org: str, repo: str, tag_name: str):
    try:
        config = await ExtensionConfig.fetch_github_release_config(org, repo, tag_name)
        if not config:
            return {}

        permissions = validate_extension_permissions(config.name, config.permissions)

        return {
            "min_lnbits_version": config.min_lnbits_version,
            "is_version_compatible": config.is_version_compatible(),
            "warning": config.warning,
            "extension_type": config.extension_type,
            "permissions": [dict(permission) for permission in permissions],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@extension_router.get("")
async def api_get_user_extensions(
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[Extension]:
    async with db.connect() as conn:
        user_extensions_ids = [
            ue.extension for ue in await get_user_extensions(account_id.id, conn=conn)
        ]
        valid_extensions = [
            ext
            for ext in await get_valid_extensions(False, conn=conn)
            if ext.code in user_extensions_ids
        ]
        return valid_extensions


@extension_router.delete(
    "/{ext_id}/db",
    dependencies=[Depends(check_admin)],
)
async def delete_extension_db(ext_id: str):
    try:
        db_version = await get_db_version(ext_id)
        if not db_version:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Unknown extension id: {ext_id}",
            )
        await drop_extension_db(ext_id=ext_id)
        await delete_dbversion(ext_id=ext_id)
        logger.success(f"Database removed for extension '{ext_id}'")
        return SimpleStatus(
            success=True, message=f"DB deleted for '{ext_id}' extension."
        )
    except HTTPException as ex:
        logger.error(ex)
        raise ex
    except Exception as exc:
        logger.error(exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Cannot delete data for extension '{ext_id}'",
        ) from exc


# TODO: create a response model for this
@extension_router.get("/all")
async def extensions(account_id: AccountId = Depends(check_account_id_exists)):
    async with db.connect() as conn:
        installed_exts: list[InstallableExtension] = await get_installed_extensions(
            conn=conn
        )
        all_ext_ids = [ext.code for ext in await get_valid_extensions(conn=conn)]
        inactive_extensions = [
            e.id for e in await get_installed_extensions(active=False, conn=conn)
        ]
        db_versions = await get_db_versions(conn=conn)

    installed_exts_ids = [e.id for e in installed_exts]

    installable_exts = await InstallableExtension.get_installable_extensions(
        post_refresh_cache=account_id.is_admin_id
    )
    installable_exts_ids = [e.id for e in installable_exts]
    installable_exts += [e for e in installed_exts if e.id not in installable_exts_ids]
    installable_exts.sort(key=lambda e: e.id)
    installed_exts_by_id = {e.id: e for e in installed_exts}

    for e in installable_exts:
        installed_ext = installed_exts_by_id.get(e.id)
        if installed_ext and installed_ext.meta:
            installed_release = installed_ext.meta.installed_release
            if installed_ext.meta.pay_to_enable and not account_id.is_admin_id:
                # not a security leak, but better not to share the wallet id
                installed_ext.meta.pay_to_enable.wallet = None
            pay_to_enable = installed_ext.meta.pay_to_enable

            if e.meta:
                e.meta.installed_release = installed_release
                e.meta.pay_to_enable = pay_to_enable
            else:
                e.meta = ExtensionMeta(
                    installed_release=installed_release,
                    pay_to_enable=pay_to_enable,
                )
            # use the installed extension values
            e.name = installed_ext.name
            e.short_description = installed_ext.short_description
            e.icon = installed_ext.icon

    extension_data = []
    for ext in installable_exts:
        installed_ext = installed_exts_by_id.get(ext.id)
        is_wasm = installed_ext.is_wasm if installed_ext else ext.is_wasm
        icon = wasm_extension_icon_url(ext.id) if is_wasm else ext.icon
        permissions = (
            validate_extension_permissions(
                installed_ext.id, installed_ext.permissions, strict=False
            )
            if installed_ext
            else []
        )
        extension_data.append(
            {
                "id": ext.id,
                "name": ext.name,
                "icon": icon,
                "shortDescription": ext.short_description,
                "stars": ext.stars,
                "isFeatured": ext.meta.featured if ext.meta else False,
                "categories": ext.meta.categories if ext.meta else [],
                "dependencies": ext.meta.dependencies if ext.meta else "",
                "isInstalled": ext.id in installed_exts_ids,
                "hasDatabaseTables": next(
                    (True for version in db_versions if version.db == ext.id), False
                ),
                "isAvailable": ext.id in all_ext_ids,
                "isAdminOnly": ext.id in settings.lnbits_admin_extensions,
                "isActive": ext.id not in inactive_extensions,
                "latestRelease": (
                    dict(ext.meta.latest_release)
                    if ext.meta and ext.meta.latest_release
                    else None
                ),
                "hasPaidRelease": ext.meta.has_paid_release if ext.meta else False,
                "hasFreeRelease": ext.meta.has_free_release if ext.meta else False,
                "paidFeatures": ext.meta.paid_features if ext.meta else False,
                "installedRelease": (
                    dict(ext.meta.installed_release)
                    if ext.meta and ext.meta.installed_release
                    else None
                ),
                "payToEnable": (
                    dict(ext.meta.pay_to_enable)
                    if ext.meta and ext.meta.pay_to_enable
                    else {}
                ),
                "isPaymentRequired": ext.requires_payment,
                "isWasm": is_wasm,
                "permissions": [dict(permission) for permission in permissions],
                "inProgress": False,
                "selectedForUpdate": False,
            }
        )
    return extension_data


@extension_router.get(
    "/reviews/tags",
    dependencies=[Depends(check_account_exists)],
)
async def get_extension_reviews_tags() -> list[ExtensionReviewsStatus]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.lnbits_extensions_reviews_url + "/tags")
        resp.raise_for_status()
        data = resp.json()
        return [ExtensionReviewsStatus(**item) for item in data]


@extension_router.get(
    "/reviews/{ext_id}",
    dependencies=[Depends(check_account_exists)],
)
async def get_extension_reviews(ext_id: str, request: Request) -> Page[ExtensionReview]:
    async with httpx.AsyncClient() as client:
        query_string = str(request.query_params)
        resp = await client.get(
            settings.lnbits_extensions_reviews_url + f"/reviews/{ext_id}?{query_string}"
        )
        resp.raise_for_status()
        reviews = resp.json()
        return Page(
            data=[ExtensionReview(**item) for item in reviews["data"]],
            total=reviews["total"],
        )


@extension_router.put(
    "/reviews",
    dependencies=[Depends(check_account_exists)],
)
async def create_extension_review(
    data: CreateExtensionReview,
) -> ExtensionReviewPaymentRequest:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.lnbits_extensions_reviews_url + "/reviews", json=data.dict()
        )
        resp.raise_for_status()
        payment_request = resp.json()
        return ExtensionReviewPaymentRequest(**payment_request)


def _load_installed_extension_config(extension: InstallableExtension) -> dict:
    ext_dir = extension.wasm_ext_dir if extension.is_wasm else extension.ext_dir
    config_path = ext_dir / "config.json"
    if not config_path.is_file():
        raise ValueError(f"Extension '{extension.id}' config file is missing.")
    try:
        with open(config_path, encoding="utf-8") as config_file:
            config = json.load(config_file)
    except Exception as exc:
        raise ValueError(f"Cannot read extension config for '{extension.id}'.") from exc
    if not isinstance(config, dict):
        raise ValueError(f"Extension '{extension.id}' config file is invalid.")
    return config


async def _require_active_wasm_extension(ext_id: str) -> InstallableExtension:
    installed_ext = await get_installed_extension(ext_id)
    if not installed_ext or not installed_ext.active:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' is not active."
        )
    if not installed_ext.is_wasm:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, f"Extension '{ext_id}' is not a WASM extension."
        )
    return installed_ext


def _safe_user_extension_permissions(permissions: dict | None) -> dict:
    safe_permissions: dict[str, list[dict]] = {}
    for permission_id, grants in (permissions or {}).items():
        if not isinstance(permission_id, str) or not isinstance(grants, list):
            continue
        safe_grants = [
            grant
            for grant in grants
            if isinstance(grant, dict) and isinstance(grant.get("id"), str)
        ]
        if safe_grants:
            safe_permissions[permission_id] = safe_grants
    return safe_permissions


def _user_permission_grant_id_for_wallet(
    permissions: dict, permission_id: str, wallet_id: str
) -> str | None:
    grants = permissions.get(permission_id)
    if not isinstance(grants, list):
        return None

    for grant in grants:
        if not isinstance(grant, dict) or grant.get("wallet_id") != wallet_id:
            continue
        grant_id = grant.get("id")
        return grant_id if isinstance(grant_id, str) and grant_id else None
    return None


def _remove_user_permission_grant(permissions: dict, grant_id: str) -> dict:
    updated_permissions = dict(permissions or {})
    for permission_id, grants in list(updated_permissions.items()):
        if not isinstance(grants, list):
            continue

        remaining_grants = [
            grant
            for grant in grants
            if not isinstance(grant, dict) or grant.get("id") != grant_id
        ]
        if remaining_grants:
            updated_permissions[permission_id] = remaining_grants
        else:
            updated_permissions.pop(permission_id, None)
    return updated_permissions


async def _check_background_payment_permission(
    account_id: str,
    permissions: dict,
    grant_data: dict,
) -> ExtensionPermissionCheckResult:
    try:
        data = ExtensionBackgroundPaymentGrantRequest.parse_obj(grant_data)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc

    wallet = await get_wallet(data.wallet_id)
    if not wallet or wallet.user != account_id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your wallet.")
    if wallet.is_lightning_shared_wallet:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "Background payments are not allowed from shared wallets.",
        )
    if not wallet.can_send_payments:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "This wallet cannot send payments.",
        )

    requested_grant = data.to_grant()
    existing_grant = _find_background_payment_grant(
        permissions, requested_grant.wallet_id
    )
    covered = (
        existing_grant is not None
        and existing_grant.enabled
        and existing_grant.max_amount >= requested_grant.max_amount
        and _background_destination_policy_covers(
            existing_grant.destination_policy, requested_grant.destination_policy
        )
    )
    grant = existing_grant if covered and existing_grant else requested_grant
    return ExtensionPermissionCheckResult(
        id=WALLET_PAY_INVOICE_BACKGROUND_PERMISSION,
        approved=covered,
        grant=json.loads(grant.json()),
    )


async def _check_wallet_payments_watch_permission(
    account_id: str,
    permissions: dict,
    grant_data: dict,
) -> ExtensionPermissionCheckResult:
    try:
        data = ExtensionWalletPaymentsWatchGrantRequest.parse_obj(grant_data)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc

    wallet = await get_wallet(data.wallet_id)
    if not wallet or wallet.user != account_id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not your wallet.")

    existing_grant = _find_wallet_payments_watch_grant(permissions, data.wallet_id)
    covered = bool(existing_grant and existing_grant.enabled)
    grant = existing_grant if covered and existing_grant else data.to_grant()
    return ExtensionPermissionCheckResult(
        id=WALLET_PAYMENTS_WATCH_PERMISSION,
        approved=covered,
        grant=json.loads(grant.json()),
    )


def _find_background_payment_grant(
    permissions: dict, wallet_id: str
) -> ExtensionBackgroundPaymentGrant | None:
    grants = permissions.get(WALLET_PAY_INVOICE_BACKGROUND_PERMISSION)
    if not isinstance(grants, list):
        return None
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


def _find_wallet_payments_watch_grant(
    permissions: dict, wallet_id: str
) -> ExtensionWalletPaymentsWatchGrant | None:
    grants = permissions.get(WALLET_PAYMENTS_WATCH_PERMISSION)
    if not isinstance(grants, list):
        return None
    for grant_data in grants:
        if not isinstance(grant_data, dict):
            continue
        try:
            grant = ExtensionWalletPaymentsWatchGrant.parse_obj(grant_data)
        except ValueError:
            continue
        if grant.wallet_id == wallet_id:
            return grant
    return None


def _background_destination_policy_covers(
    existing: ExtensionBackgroundPaymentDestinationPolicy,
    requested: ExtensionBackgroundPaymentDestinationPolicy,
) -> bool:
    return (
        existing == requested
        or existing == ExtensionBackgroundPaymentDestinationPolicy.EXTERNAL_ALLOWED
    )
