import base64
import json
import time
from http import HTTPStatus
from typing import List, Optional
from uuid import uuid4

import shortuuid
from fastapi import APIRouter, Body, Depends
from fastapi.exceptions import HTTPException

from lnbits.core.crud import (
    create_wallet,
    delete_account,
    delete_wallet,
    force_delete_wallet,
    get_account,
    get_accounts,
    get_wallet,
    get_wallets,
    update_admin_settings,
    update_wallet,
)
from lnbits.core.models import (
    AccountFilters,
    AccountOverview,
    CreateTopup,
    CreateUser,
    User,
    UserExtra,
    Wallet,
)
from lnbits.core.models.users import Account
from lnbits.core.services import (
    create_user_account_no_ckeck,
    update_user_account,
    update_wallet_balance,
)
from lnbits.db import Filters, Page
from lnbits.decorators import check_admin, check_super_user, parse_filters
from lnbits.helpers import (
    encrypt_internal_message,
    generate_filter_params_openapi,
)
from lnbits.settings import EditableSettings, settings
from lnbits.utils.exchange_rates import allowed_currencies

users_router = APIRouter(prefix="/users/api/v1", dependencies=[Depends(check_admin)])


@users_router.get(
    "/user",
    name="get accounts",
    summary="Get paginated list of accounts",
    openapi_extra=generate_filter_params_openapi(AccountFilters),
)
async def api_get_users(
    filters: Filters = Depends(parse_filters(AccountFilters)),
) -> Page[AccountOverview]:
    return await get_accounts(filters=filters)


@users_router.get("/user/{user_id}")
async def api_get_user(user_id: str) -> Account:
    account = await get_account(user_id)
    if not account:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Username not found.")
    return account


@users_router.post("/user")
async def api_create_user(data: CreateUser) -> CreateUser:
    if not data.username and data.password:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Username required when password provided."
        )

    if data.password != data.password_repeat:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Passwords do not match.")

    if not data.password:
        random_password = shortuuid.uuid()
        data.password = random_password
        data.password_repeat = random_password
    data.extra = data.extra or UserExtra()
    data.extra.provider = data.extra.provider or "lnbits"

    account = Account(
        id=uuid4().hex,
        username=data.username,
        email=data.email,
        pubkey=data.pubkey,
        extra=data.extra,
    )
    account.validate_fields()
    account.hash_password(data.password)
    user = await create_user_account_no_ckeck(account)
    data.id = user.id
    return data


@users_router.put("/user/{user_id}")
async def api_update_user(user_id: str, data: CreateUser) -> CreateUser:
    if user_id != data.id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "User Id missmatch.")

    if data.password or data.password_repeat:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Use 'reset password' functionality."
        )

    account = Account(
        id=user_id,
        username=data.username,
        email=data.email,
        pubkey=data.pubkey,
        extra=data.extra or UserExtra(),
    )
    await update_user_account(account)

    return data


@users_router.delete("/user/{user_id}", status_code=HTTPStatus.OK)
async def api_users_delete_user(
    user_id: str, user: User = Depends(check_admin)
) -> None:
    wallets = await get_wallets(user_id)
    if len(wallets) > 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot delete user with wallets.",
        )

    if user_id == settings.super_user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot delete super user.",
        )

    if user_id in settings.lnbits_admin_users and not user.super_user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Only super_user can delete admin user.",
        )
    await delete_account(user_id)


@users_router.put(
    "/user/{user_id}/reset_password", dependencies=[Depends(check_super_user)]
)
async def api_users_reset_password(user_id: str) -> str:
    if user_id == settings.super_user:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Cannot change superuser password.",
        )

    reset_data = ["reset", user_id, int(time.time())]
    reset_data_json = json.dumps(reset_data, separators=(",", ":"), ensure_ascii=False)
    reset_key = encrypt_internal_message(reset_data_json)
    assert reset_key, "Cannot generate reset key."
    reset_key_b64 = base64.b64encode(reset_key.encode()).decode()
    return f"reset_key_{reset_key_b64}"


@users_router.get("/user/{user_id}/admin", dependencies=[Depends(check_super_user)])
async def api_users_toggle_admin(user_id: str) -> None:
    if user_id == settings.super_user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot change super user.",
        )
    if user_id in settings.lnbits_admin_users:
        settings.lnbits_admin_users.remove(user_id)
    else:
        settings.lnbits_admin_users.append(user_id)
    update_settings = EditableSettings(lnbits_admin_users=settings.lnbits_admin_users)
    await update_admin_settings(update_settings)


@users_router.get("/user/{user_id}/wallet")
async def api_users_get_user_wallet(user_id: str) -> List[Wallet]:
    return await get_wallets(user_id)


@users_router.post("/user/{user_id}/wallet")
async def api_users_create_user_wallet(
    user_id: str, name: Optional[str] = Body(None), currency: Optional[str] = Body(None)
):
    if currency and currency not in allowed_currencies():
        raise ValueError(f"Currency '{currency}' not allowed")

    wallet = await create_wallet(user_id=user_id, wallet_name=name)

    if currency:
        wallet.currency = currency
        await update_wallet(wallet)

    return wallet


@users_router.get("/user/{user_id}/wallet/{wallet}/undelete")
async def api_users_undelete_user_wallet(user_id: str, wallet: str) -> None:
    # TODO: find this in the UI
    wal = await get_wallet(wallet)
    if not wal:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Wallet does not exist.",
        )

    if user_id != wal.user:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Wallet does not belong to user.",
        )
    if wal.deleted:
        await delete_wallet(user_id=user_id, wallet_id=wallet, deleted=False)


@users_router.delete("/user/{user_id}/wallet/{wallet}")
async def api_users_delete_user_wallet(user_id: str, wallet: str) -> None:
    wal = await get_wallet(wallet)
    if not wal:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Wallet does not exist.",
        )
    if wal.deleted:
        await force_delete_wallet(wallet)
    await delete_wallet(user_id=user_id, wallet_id=wallet)


@users_router.put(
    "/topup",
    name="Topup",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_topup_balance(data: CreateTopup) -> dict[str, str]:
    await get_wallet(data.id)
    if settings.lnbits_backend_wallet_class == "VoidWallet":
        raise Exception("VoidWallet active")

    await update_wallet_balance(wallet_id=data.id, amount=int(data.amount))
    return {"status": "Success"}
