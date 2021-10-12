from http import HTTPStatus
from starlette.exceptions import HTTPException

from fastapi import Query
from fastapi.params import Depends

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.decorators import WalletTypeInfo, get_key_type

from . import usermanager_ext
from .models import CreateUserData
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


@usermanager_ext.get("/api/v1/users", status_code=HTTPStatus.OK)
async def api_usermanager_users(wallet: WalletTypeInfo = Depends(get_key_type)):
    user_id = wallet.wallet.user
    return [user.dict() for user in await get_usermanager_users(user_id)]


@usermanager_ext.get("/api/v1/users/{user_id}", status_code=HTTPStatus.OK)
async def api_usermanager_user(user_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    user = await get_usermanager_user(user_id)
    return user.dict()


@usermanager_ext.post("/api/v1/users", status_code=HTTPStatus.CREATED)
# @api_validate_post_request(
#     schema={
#         "user_name": {"type": "string", "empty": False, "required": True},
#         "wallet_name": {"type": "string", "empty": False, "required": True},
#         "admin_id": {"type": "string", "empty": False, "required": True},
#         "email": {"type": "string", "required": False},
#         "password": {"type": "string", "required": False},
#     }
# )
async def api_usermanager_users_create(data: CreateUserData, wallet: WalletTypeInfo = Depends(get_key_type)):
    user = await create_usermanager_user(**data)
    full = user.dict()
    full["wallets"] = [wallet.dict() for wallet in await get_usermanager_users_wallets(user.id)]
    return full


@usermanager_ext.delete("/api/v1/users/{user_id}")
async def api_usermanager_users_delete(user_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    user = await get_usermanager_user(user_id)
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="User does not exist."
        )
    await delete_usermanager_user(user_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


###Activate Extension


@usermanager_ext.post("/api/v1/extensions")
async def api_usermanager_activate_extension(extension: str = Query(...), userid: str = Query(...), active: bool = Query(...)):
    user = await get_user(userid)
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="User does not exist."
        )
    update_user_extension(
        user_id=userid, extension=extension, active=active
    )
    return {"extension": "updated"}


###Wallets


@usermanager_ext.route("/api/v1/wallets", methods=["POST"])
@api_check_wallet_key(key_type="invoice")
@api_validate_post_request(
    schema={
        "user_id": {"type": "string", "empty": False, "required": True},
        "wallet_name": {"type": "string", "empty": False, "required": True},
        "admin_id": {"type": "string", "empty": False, "required": True},
    }
)
async def api_usermanager_wallets_create():
    user = await create_usermanager_wallet(
        g.data["user_id"], g.data["wallet_name"], g.data["admin_id"]
    )
    return jsonify(user._asdict()), HTTPStatus.CREATED


@usermanager_ext.route("/api/v1/wallets", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_wallets():
    admin_id = g.wallet.user
    return (
        jsonify(
            [wallet._asdict() for wallet in await get_usermanager_wallets(admin_id)]
        ),
        HTTPStatus.OK,
    )


@usermanager_ext.route("/api/v1/wallets<wallet_id>", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_wallet_transactions(wallet_id):
    return jsonify(await get_usermanager_wallet_transactions(wallet_id)), HTTPStatus.OK


@usermanager_ext.route("/api/v1/wallets/<user_id>", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_users_wallets(user_id):
    wallet = await get_usermanager_users_wallets(user_id)
    return (
        jsonify(
            [
                wallet._asdict()
                for wallet in await get_usermanager_users_wallets(user_id)
            ]
        ),
        HTTPStatus.OK,
    )


@usermanager_ext.route("/api/v1/wallets/<wallet_id>", methods=["DELETE"])
@api_check_wallet_key(key_type="invoice")
async def api_usermanager_wallets_delete(wallet_id):
    wallet = await get_usermanager_wallet(wallet_id)
    if not wallet:
        return jsonify({"message": "Wallet does not exist."}), HTTPStatus.NOT_FOUND

    await delete_usermanager_wallet(wallet_id, wallet.user)
    return "", HTTPStatus.NO_CONTENT
