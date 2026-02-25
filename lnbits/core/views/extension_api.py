import json
import sys
import traceback
from http import HTTPStatus
from pathlib import Path

import httpx
from bolt11 import decode as bolt11_decode
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.requests import Request
from loguru import logger
from starlette.routing import Match

from lnbits.core.crud.extensions import get_user_extensions
from lnbits.core.crud.wallets import get_wallets_ids
from lnbits.core.db import db
from lnbits.core.models import (
    SimpleStatus,
)
from lnbits.core.models.extensions import (
    CreateExtension,
    CreateExtensionReview,
    Extension,
    ExtensionConfig,
    ExtensionMeta,
    ExtensionPermission,
    ExtensionPermissionsGrant,
    ExtensionRelease,
    ExtensionReview,
    ExtensionReviewPaymentRequest,
    ExtensionReviewsStatus,
    InstallableExtension,
    PayToEnableInfo,
    ReleasePaymentInfo,
    UserExtension,
    UserExtensionInfo,
)
from lnbits.core.models.users import Account, AccountId
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.core.services.extensions import (
    activate_extension,
    deactivate_extension,
    get_valid_extension,
    get_valid_extensions,
    install_extension,
    uninstall_extension,
)
from lnbits.core.wasm import WASM_HOST_MANIFEST
from lnbits.core.wasm.extension_host import (
    clear_schedules_for_user,
    clear_tag_watches_for_user,
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
        extension = await install_extension(ext_info)

    except Exception as exc:
        logger.warning(exc)
        etype, _, tb = sys.exc_info()
        traceback.print_exception(etype, exc, tb)
        ext_info.clean_extension_files()
        detail = (
            str(exc)
            if isinstance(exc, AssertionError)
            else f"Failed to install extension '{ext_info.id}'."
            f"({ext_info.installed_version})."
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
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
    ext_id: str,
    request: Request,
    account_id: AccountId = Depends(check_account_id_exists),
    grant: ExtensionPermissionsGrant | None = Body(default=None),
) -> SimpleStatus:
    await _ensure_extension_exists(ext_id)
    logger.info(f"Enabling extension: {ext_id}.")

    ext = await _get_installed_active_extension(ext_id)
    user_ext = await _get_or_create_user_extension(account_id.id, ext_id)

    required_permissions = _get_required_permissions(ext_id, ext)
    granted_permissions = _get_granted_permissions(grant, user_ext)
    granted_tags = _get_granted_payment_tags(grant, user_ext)
    required_tags = _get_required_payment_tags(ext_id, ext)
    if _is_wasm_extension(ext_id, ext):
        _ensure_api_permissions_available(
            request, _merge_permissions(required_permissions, granted_permissions)
        )
        _ensure_payment_tags_allowed(required_tags, granted_tags)
    _ensure_permissions(required_permissions, granted_permissions)

    if grant and grant.permissions:
        await _store_granted_permissions(user_ext, granted_permissions)
    if grant and grant.payment_tags:
        await _store_granted_payment_tags(user_ext, granted_tags)

    if account_id.is_admin_id or not ext.requires_payment:
        await _activate_user_extension(user_ext)
        return SimpleStatus(success=True, message=f"Extension '{ext_id}' enabled.")

    return await _enable_paid_extension(ext_id, ext, user_ext)


async def _ensure_extension_exists(ext_id: str) -> None:
    if ext_id not in [e.code for e in await get_valid_extensions()]:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' doesn't exist."
        )


async def _get_installed_active_extension(ext_id: str) -> InstallableExtension:
    ext = await get_installed_extension(ext_id)
    if not ext:
        raise ValueError(f"Extension '{ext_id}' is not installed.")
    if not ext.active:
        raise ValueError(f"Extension '{ext_id}' is not activated.")
    return ext


async def _get_or_create_user_extension(user_id: str, ext_id: str) -> UserExtension:
    user_ext = await get_user_extension(user_id, ext_id)
    if not user_ext:
        user_ext = UserExtension(user=user_id, extension=ext_id, active=False)
        await create_user_extension(user_ext)
    return user_ext


def _get_required_permissions(ext_id: str, ext: InstallableExtension) -> list[str]:
    permissions_source = (
        ext.meta.permissions
        if ext.meta and ext.meta.permissions
        else _load_permissions_from_config(ext_id)
    )
    return [p.id for p in permissions_source] if permissions_source else []


def _get_granted_permissions(
    grant: ExtensionPermissionsGrant | None, user_ext: UserExtension
) -> list[str]:
    if grant and grant.permissions:
        return grant.permissions
    if user_ext.extra and user_ext.extra.granted_permissions:
        return user_ext.extra.granted_permissions
    return []


def _get_required_payment_tags(ext_id: str, ext: InstallableExtension) -> list[str]:
    tags_source = (
        ext.meta.payment_tags
        if ext.meta and ext.meta.payment_tags
        else _load_payment_tags_from_config(ext_id)
    )
    return tags_source if tags_source else []


def _get_granted_payment_tags(
    grant: ExtensionPermissionsGrant | None, user_ext: UserExtension
) -> list[str]:
    if grant and grant.payment_tags:
        return grant.payment_tags
    if user_ext.extra and user_ext.extra.granted_payment_tags:
        return user_ext.extra.granted_payment_tags
    return []


def _ensure_permissions(required: list[str], granted: list[str]) -> None:
    if not required:
        return
    missing = [p for p in required if p not in granted]
    if missing:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "Missing required permissions to enable this extension.",
        )


async def _store_granted_permissions(
    user_ext: UserExtension, granted_permissions: list[str]
) -> None:
    user_ext_info = user_ext.extra or UserExtensionInfo()
    user_ext_info.granted_permissions = granted_permissions
    user_ext.extra = user_ext_info
    await update_user_extension(user_ext)


async def _store_granted_payment_tags(
    user_ext: UserExtension, granted_tags: list[str]
) -> None:
    user_ext_info = user_ext.extra or UserExtensionInfo()
    user_ext_info.granted_payment_tags = granted_tags
    user_ext.extra = user_ext_info
    await update_user_extension(user_ext)


async def _activate_user_extension(user_ext: UserExtension) -> None:
    user_ext.active = True
    await update_user_extension(user_ext)


async def _enable_paid_extension(
    ext_id: str, ext: InstallableExtension, user_ext: UserExtension
) -> SimpleStatus:
    if not (user_ext.extra and user_ext.extra.payment_hash_to_enable):
        raise HTTPException(
            HTTPStatus.PAYMENT_REQUIRED, f"Extension '{ext_id}' requires payment."
        )

    if user_ext.is_paid:
        await _activate_user_extension(user_ext)
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

    user_ext.extra.paid_to_enable = True
    await _activate_user_extension(user_ext)
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
    if user_ext.extra and user_ext.extra.granted_permissions:
        user_ext.extra.granted_permissions = []
    if user_ext.extra and user_ext.extra.granted_payment_tags:
        user_ext.extra.granted_payment_tags = []
    await update_user_extension(user_ext)
    ext = await get_installed_extension(ext_id)
    if ext and ext.meta and ext.meta.extension_type == "wasm":
        await clear_tag_watches_for_user(ext_id, account_id.id)
        await clear_schedules_for_user(ext_id, account_id.id)
    return SimpleStatus(success=True, message=f"Extension '{ext_id}' disabled.")


@extension_router.put("/{ext_id}/permissions")
async def api_update_extension_permissions(
    ext_id: str,
    request: Request,
    account_id: AccountId = Depends(check_account_id_exists),
    grant: ExtensionPermissionsGrant | None = Body(default=None),
) -> SimpleStatus:
    if ext_id not in [e.code for e in await get_valid_extensions()]:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Extension '{ext_id}' doesn't exist."
        )

    ext = await get_installed_extension(ext_id)
    if not ext:
        raise ValueError(f"Extension '{ext_id}' is not installed.")
    if not ext.active:
        raise ValueError(f"Extension '{ext_id}' is not activated.")

    user_ext = await get_user_extension(account_id.id, ext_id)
    if not user_ext:
        user_ext = UserExtension(user=account_id.id, extension=ext_id, active=False)
        await create_user_extension(user_ext)

    permissions_source = (
        ext.meta.permissions
        if ext.meta and ext.meta.permissions
        else _load_permissions_from_config(ext_id)
    )
    required_permissions = (
        [p.id for p in permissions_source] if permissions_source else []
    )
    granted_permissions = grant.permissions if grant and grant.permissions else []
    granted_tags = grant.payment_tags if grant and grant.payment_tags else []
    if _is_wasm_extension(ext_id, ext):
        _ensure_api_permissions_available(
            request, _merge_permissions(required_permissions, granted_permissions)
        )
        _ensure_payment_tags_allowed(
            _get_required_payment_tags(ext_id, ext), granted_tags
        )

    if required_permissions:
        missing = [p for p in required_permissions if p not in granted_permissions]
        if missing:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                "Missing required permissions to save for this extension.",
            )

    user_ext_info = user_ext.extra or UserExtensionInfo()
    user_ext_info.granted_permissions = granted_permissions
    user_ext_info.granted_payment_tags = granted_tags
    user_ext.extra = user_ext_info
    await update_user_extension(user_ext)

    return SimpleStatus(success=True, message=f"Permissions saved for '{ext_id}'.")


@extension_router.get("/{ext_id}/capabilities")
async def api_extension_capabilities(
    ext_id: str,
    request: Request,
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    await _ensure_extension_exists(ext_id)
    ext = await get_installed_extension(ext_id)
    if not ext:
        raise ValueError(f"Extension '{ext_id}' is not installed.")

    permissions_source = (
        ext.meta.permissions
        if ext.meta and ext.meta.permissions
        else _load_permissions_from_config(ext_id)
    )
    permissions = [p.id for p in permissions_source] if permissions_source else []
    missing = (
        _missing_api_permissions(request, permissions)
        if _is_wasm_extension(ext_id, ext)
        else []
    )
    payment_tags = _get_required_payment_tags(ext_id, ext)

    return {
        "ok": True,
        "extension": ext_id,
        "is_wasm": _is_wasm_extension(ext_id, ext),
        "permissions": permissions,
        "missing_permissions": missing,
        "payment_tags": payment_tags,
    }


@extension_router.get("/wasm/manifest")
async def api_wasm_manifest(
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    return WASM_HOST_MANIFEST


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

        return {
            "min_lnbits_version": config.min_lnbits_version,
            "is_version_compatible": config.is_version_compatible(),
            "warning": config.warning,
        }
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
        user_exts = await get_user_extensions(account_id.id, conn=conn)
        all_ext_ids = [ext.code for ext in await get_valid_extensions(conn=conn)]
        inactive_extensions = [
            e.id for e in await get_installed_extensions(active=False, conn=conn)
        ]
        db_versions = await get_db_versions(conn=conn)

    installed_exts_ids = [e.id for e in installed_exts]
    user_exts_map = {e.extension: e for e in user_exts}

    installable_exts = await InstallableExtension.get_installable_extensions(
        post_refresh_cache=account_id.is_admin_id
    )
    installable_exts_ids = [e.id for e in installable_exts]
    installable_exts += [e for e in installed_exts if e.id not in installable_exts_ids]

    for e in installable_exts:
        installed_ext = next((ie for ie in installed_exts if e.id == ie.id), None)
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
        if e.meta and not e.meta.permissions:
            e.meta.permissions = _load_permissions_from_config(e.id)
        if e.meta and not e.meta.payment_tags:
            e.meta.payment_tags = _load_payment_tags_from_config(e.id)

    extension_data = [
        {
            "id": ext.id,
            "name": ext.name,
            "icon": ext.icon,
            "shortDescription": ext.short_description,
            "stars": ext.stars,
            "isFeatured": ext.meta.featured if ext.meta else False,
            "dependencies": ext.meta.dependencies if ext.meta else "",
            "isInstalled": ext.id in installed_exts_ids,
            "hasDatabaseTables": next(
                (True for version in db_versions if version.db == ext.id), False
            ),
            "isAvailable": ext.id in all_ext_ids,
            "isAdminOnly": ext.id in settings.lnbits_admin_extensions,
            "isActive": ext.id not in inactive_extensions,
            "permissions": (
                [dict(p) for p in ext.meta.permissions]
                if ext.meta and ext.meta.permissions
                else [dict(p) for p in _load_permissions_from_config(ext.id)]
            ),
            "paymentTags": (
                ext.meta.payment_tags
                if ext.meta and ext.meta.payment_tags
                else _load_payment_tags_from_config(ext.id)
            ),
            "kvSchema": _load_kv_schema_from_config(ext.id),
            "grantedPermissions": (
                user_ext.extra.granted_permissions
                if (user_ext := user_exts_map.get(ext.id)) and user_ext.extra
                else []
            ),
            "grantedPaymentTags": (
                user_ext.extra.granted_payment_tags
                if (user_ext := user_exts_map.get(ext.id)) and user_ext.extra
                else []
            ),
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
            "inProgress": False,
            "selectedForUpdate": False,
        }
        for ext in installable_exts
    ]
    return extension_data


def _load_permissions_from_config(ext_id: str) -> list[ExtensionPermission]:
    try:
        conf_path = Path(
            settings.lnbits_extensions_path, "extensions", ext_id, "config.json"
        )
        if not conf_path.is_file():
            return []
        with open(conf_path, "r+") as json_file:
            config_json = json.load(json_file)
        permissions = config_json.get("permissions", [])
        return [ExtensionPermission(**p) for p in permissions]
    except Exception:
        return []


def _load_kv_schema_from_config(ext_id: str) -> dict:
    try:
        conf_path = Path(
            settings.lnbits_extensions_path, "extensions", ext_id, "config.json"
        )
        if not conf_path.is_file():
            return {}
        with open(conf_path, "r+") as json_file:
            config_json = json.load(json_file)
        schema = config_json.get("kv_schema", {})
        return schema if isinstance(schema, dict) else {}
    except Exception:
        return {}


def _load_payment_tags_from_config(ext_id: str) -> list[str]:
    try:
        conf_path = Path(
            settings.lnbits_extensions_path, "extensions", ext_id, "config.json"
        )
        if not conf_path.is_file():
            return []
        with open(conf_path, "r+") as json_file:
            config_json = json.load(json_file)
        tags = config_json.get("payment_tags", [])
        return tags if isinstance(tags, list) else []
    except Exception:
        return []


def _merge_permissions(required: list[str], granted: list[str]) -> list[str]:
    merged = set()
    for perm in required or []:
        merged.add(perm)
    for perm in granted or []:
        merged.add(perm)
    return list(merged)


def _ensure_payment_tags_allowed(required: list[str], granted: list[str]) -> None:
    if not required and granted:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "This extension does not declare any payment tags.",
        )
    if not required or not granted:
        return
    invalid = [t for t in granted if t not in required]
    if invalid:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            f"Invalid payment tags requested: {', '.join(invalid)}",
        )


def _ensure_api_permissions_available(request: Request, permissions: list[str]) -> None:
    if not permissions:
        return
    missing = []
    for perm in permissions:
        parsed = _parse_api_permission(perm)
        if not parsed:
            continue
        method, path = parsed
        if not _route_exists(request, method, path):
            missing.append(perm)
    if missing:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            f"Permissions reference missing endpoints: {', '.join(missing)}",
        )


def _parse_api_permission(perm: str) -> tuple[str, str] | None:
    if not perm.startswith("api."):
        return None
    try:
        method_part, path = perm.split(":", 1)
        method = method_part.replace("api.", "").upper()
    except ValueError:
        return None
    if not path.startswith("/"):
        return None
    return method, path


def _missing_api_permissions(request: Request, permissions: list[str]) -> list[str]:
    missing = []
    for perm in permissions or []:
        parsed = _parse_api_permission(perm)
        if not parsed:
            continue
        method, path = parsed
        if not _route_exists(request, method, path):
            missing.append(perm)
    return missing


def _route_exists(request: Request, method: str, path: str) -> bool:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "headers": [],
    }
    for route in request.app.router.routes:
        methods = getattr(route, "methods", None)
        if methods and method not in methods:
            continue
        try:
            match, _ = route.matches(scope)
        except Exception as exc:
            logger.debug(f"Route match failed for {method} {path}: {exc!s}")
            continue
        if match == Match.FULL:
            return True
    return False


def _is_wasm_extension(ext_id: str, ext: InstallableExtension) -> bool:
    if ext.meta and ext.meta.extension_type == "wasm":
        return True
    try:
        conf_path = Path(
            settings.lnbits_extensions_path, "extensions", ext_id, "config.json"
        )
        if not conf_path.is_file():
            return False
        with open(conf_path, "r+") as json_file:
            config_json = json.load(json_file)
        return config_json.get("extension_type") == "wasm"
    except Exception:
        return False


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
