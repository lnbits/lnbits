from http import HTTPStatus

from fastapi import Depends, Query
from starlette.exceptions import HTTPException

from lnbits.core import update_user_extension
from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import usermanager_ext
from .crud import (
    create_usermanager_user,
    create_usermanager_wallet,
    delete_usermanager_user,
    delete_usermanager_wallet,
    get_usermanager_user,
    get_usermanager_users,
    get_usermanager_users_wallets,
    get_usermanager_wallet,
    get_usermanager_wallet_transactions,
    get_usermanager_wallets,
)
from .models import CreateUserData, CreateUserWallet


@usermanager_ext.get("/api/v1/users", status_code=HTTPStatus.OK)
async def api_usermanager_users(
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    user_id = wallet.wallet.user
    return [user.dict() for user in await get_usermanager_users(user_id)]


@usermanager_ext.get(
    "/api/v1/users/{user_id}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(get_key_type)],
)
async def api_usermanager_user(user_id):
    user = await get_usermanager_user(user_id)
    return user.dict() if user else None


@usermanager_ext.post(
    "/api/v1/users",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(get_key_type)],
)
async def api_usermanager_users_create(data: CreateUserData):
    user = await create_usermanager_user(data)
    full = user.dict()
    full["wallets"] = [
        wallet.dict() for wallet in await get_usermanager_users_wallets(user.id)
    ]
    return full


@usermanager_ext.delete(
    "/api/v1/users/{user_id}", dependencies=[Depends(require_admin_key)]
)
async def api_usermanager_users_delete(
    user_id,
    delete_core: bool = Query(True),
):
    user = await get_usermanager_user(user_id)
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="User does not exist."
        )
    await delete_usermanager_user(user_id, delete_core)
    return "", HTTPStatus.NO_CONTENT


# Activate Extension


@usermanager_ext.post("/api/v1/extensions")
async def api_usermanager_activate_extension(
    extension: str = Query(...), userid: str = Query(...), active: bool = Query(...)
):
    user = await get_user(userid)
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="User does not exist."
        )
    await update_user_extension(user_id=userid, extension=extension, active=active)
    return {"extension": "updated"}


# Wallets


@usermanager_ext.post("/api/v1/wallets", dependencies=[Depends(get_key_type)])
async def api_usermanager_wallets_create(data: CreateUserWallet):
    user = await create_usermanager_wallet(
        user_id=data.user_id, wallet_name=data.wallet_name, admin_id=data.admin_id
    )
    return user.dict()


@usermanager_ext.get("/api/v1/wallets")
async def api_usermanager_wallets(
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    admin_id = wallet.wallet.user
    return [wallet.dict() for wallet in await get_usermanager_wallets(admin_id)]


@usermanager_ext.get(
    "/api/v1/transactions/{wallet_id}", dependencies=[Depends(get_key_type)]
)
async def api_usermanager_wallet_transactions(wallet_id):
    return await get_usermanager_wallet_transactions(wallet_id)


@usermanager_ext.get(
    "/api/v1/wallets/{user_id}", dependencies=[Depends(require_admin_key)]
)
async def api_usermanager_users_wallets(user_id):
    return [
        s_wallet.dict() for s_wallet in await get_usermanager_users_wallets(user_id)
    ]


@usermanager_ext.delete(
    "/api/v1/wallets/{wallet_id}", dependencies=[Depends(require_admin_key)]
)
async def api_usermanager_wallets_delete(wallet_id):
    get_wallet = await get_usermanager_wallet(wallet_id)
    if not get_wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )
    await delete_usermanager_wallet(wallet_id, get_wallet.user)
    return "", HTTPStatus.NO_CONTENT
