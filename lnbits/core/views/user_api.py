from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import (
    delete_account,
    delete_wallet,
    force_delete_wallet,
    get_accounts,
    get_wallet,
    get_wallets,
    update_admin_settings,
)
from lnbits.core.models import (
    Account,
    AccountFilters,
    CreateTopup,
    User,
    Wallet,
)
from lnbits.core.services import update_wallet_balance
from lnbits.db import Filters, Page
from lnbits.decorators import check_admin, check_super_user, parse_filters
from lnbits.helpers import generate_filter_params_openapi
from lnbits.settings import EditableSettings, settings

users_router = APIRouter(prefix="/users/api/v1", dependencies=[Depends(check_admin)])


@users_router.get(
    "/user",
    name="get accounts",
    summary="Get paginated list of accounts",
    openapi_extra=generate_filter_params_openapi(AccountFilters),
)
async def api_get_users(
    filters: Filters = Depends(parse_filters(AccountFilters)),
) -> Page[Account]:
    try:
        filtered = await get_accounts(filters=filters)
        for user in filtered.data:
            user.is_super_user = user.id == settings.super_user
            user.is_admin = user.id in settings.lnbits_admin_users or user.is_super_user
        return filtered
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Could not fetch users. {exc!s}",
        ) from exc


@users_router.delete("/user/{user_id}", status_code=HTTPStatus.OK)
async def api_users_delete_user(
    user_id: str, user: User = Depends(check_admin)
) -> None:

    try:
        wallets = await get_wallets(user_id)
        if len(wallets) > 0:
            raise Exception("Cannot delete user with wallets.")
        if user_id == settings.super_user:
            raise Exception("Cannot delete super user.")

        if user_id in settings.lnbits_admin_users and not user.super_user:
            raise Exception("Only super_user can delete admin user.")

        await delete_account(user_id)

    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"{exc!s}",
        ) from exc


@users_router.get("/user/{user_id}/admin", dependencies=[Depends(check_super_user)])
async def api_users_toggle_admin(user_id: str) -> None:
    try:
        if user_id == settings.super_user:
            raise Exception("Cannot change super user.")
        if user_id in settings.lnbits_admin_users:
            settings.lnbits_admin_users.remove(user_id)
        else:
            settings.lnbits_admin_users.append(user_id)
        update_settings = EditableSettings(
            lnbits_admin_users=settings.lnbits_admin_users
        )
        await update_admin_settings(update_settings)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Could not update admin settings. {exc}",
        ) from exc


@users_router.get("/user/{user_id}/wallet")
async def api_users_get_user_wallet(user_id: str) -> List[Wallet]:
    try:
        return await get_wallets(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Could not fetch user wallets. {exc}",
        ) from exc


@users_router.get("/user/{user_id}/wallet/{wallet}/undelete")
async def api_users_undelete_user_wallet(user_id: str, wallet: str) -> None:
    try:
        wal = await get_wallet(wallet)
        if not wal:
            raise Exception("Wallet does not exist.")
        if user_id != wal.user:
            raise Exception("Wallet does not belong to user.")
        if wal.deleted:
            await delete_wallet(user_id=user_id, wallet_id=wallet, deleted=False)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"{exc!s}",
        ) from exc


@users_router.delete("/user/{user_id}/wallet/{wallet}")
async def api_users_delete_user_wallet(user_id: str, wallet: str) -> None:
    try:
        wal = await get_wallet(wallet)
        if not wal:
            raise Exception("Wallet does not exist.")
        if wal.deleted:
            await force_delete_wallet(wallet)
        await delete_wallet(user_id=user_id, wallet_id=wallet)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"{exc!s}",
        ) from exc


@users_router.put(
    "/topup",
    name="Topup",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_topup_balance(data: CreateTopup) -> dict[str, str]:
    try:
        await get_wallet(data.id)
        if settings.lnbits_backend_wallet_class == "VoidWallet":
            raise Exception("VoidWallet active")

        await update_wallet_balance(wallet_id=data.id, amount=int(data.amount))
        return {"status": "Success"}
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"{exc!s}"
        ) from exc
