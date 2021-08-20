from quart import g, jsonify
from http import HTTPStatus

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import usermanager_ext
from .crud import (
    create_usermanager_user,
    get_usermanager_user,
    get_usermanager_users,
    get_usermanager_wallet_transactions,
    delete_usermanager_user,
    create_usermanager_wallet,
    get_usermanager_wallet,
    get_usermanager_wallets,
    get_usermanager_users_wallets,
    delete_usermanager_wallet,
)
from lnbits.core import update_user_extension


### Users


@usermanager_ext.get("/api/v1/users")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_users():
    user_id = g.wallet.user
    return ([user._asdict() for user in await get_usermanager_users(user_id)],
        HTTPStatus.OK,
    )


@usermanager_ext.get("/api/v1/users/<user_id>")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_user(user_id):
    user = await get_usermanager_user(user_id)
    return (user._asdict(),
        HTTPStatus.OK,
    )

class CreateUsersData(BaseModel):
    domain:  str
    subdomain:  str
    email:  str
    ip:  Optional[str]
    sats:  Optional[str]

@usermanager_ext.post("/api/v1/users")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_users_create(data: CreateUsersData):
    user = await create_usermanager_user(**data)
    full = user._asdict()
    full["wallets"] = [wallet._asdict() for wallet in await get_usermanager_users_wallets(user.id)]
    return jsonify(full), HTTPStatus.CREATED


@usermanager_ext.delete("/api/v1/users/<user_id>")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_users_delete(user_id):
    user = await get_usermanager_user(user_id)
    if not user:
        return jsonify({"message": "User does not exist."}), HTTPStatus.NOT_FOUND
    await delete_usermanager_user(user_id)
    return "", HTTPStatus.NO_CONTENT


###Activate Extension

class CreateUsersData(BaseModel):
    extension:  str
    userid:  str
    active:  bool

@usermanager_ext.post("/api/v1/extensions")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_activate_extension(data: CreateUsersData):
    user = await get_user(data.userid)
    if not user:
        return {"message": "no such user"}, HTTPStatus.NOT_FOUND
    update_user_extension(
        user_id=data.userid, extension=data.extension, active=data.active
    )
    return {"extension": "updated"}, HTTPStatus.CREATED


###Wallets

class CreateWalletsData(BaseModel):
    user_id:  str
    wallet_name:  str
    admin_id:  str

@usermanager_ext.post("/api/v1/wallets")
@api_check_wallet_key(key_type="invoice")

async def api_usermanager_wallets_create(data: CreateWalletsData):
    user = await create_usermanager_wallet(
        data.user_id, data.wallet_name, data.admin_id
    )
    return user._asdict(), HTTPStatus.CREATED


@usermanager_ext.get("/api/v1/wallets")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_wallets():
    admin_id = g.wallet.user
    return (
            [wallet._asdict() for wallet in await get_usermanager_wallets(admin_id)],
        HTTPStatus.OK,
    )


@usermanager_ext.get("/api/v1/wallets<wallet_id>")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_wallet_transactions(wallet_id):
    return await get_usermanager_wallet_transactions(wallet_id), HTTPStatus.OK


@usermanager_ext.get("/api/v1/wallets/<user_id>")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_users_wallets(user_id):
    wallet = await get_usermanager_users_wallets(user_id)
    return (
            [
                wallet._asdict()
                for wallet in await get_usermanager_users_wallets(user_id)
            ],
        HTTPStatus.OK,
    )


@usermanager_ext.delete("/api/v1/wallets/<wallet_id>")
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_wallets_delete(wallet_id):
    wallet = await get_usermanager_wallet(wallet_id)
    if not wallet:
        return {"message": "Wallet does not exist."}, HTTPStatus.NOT_FOUND

    await delete_usermanager_wallet(wallet_id, wallet.user)
    return "", HTTPStatus.NO_CONTENT
