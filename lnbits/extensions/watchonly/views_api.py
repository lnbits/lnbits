import hashlib
from quart import g, jsonify, url_for, request
from http import HTTPStatus
import httpx
import json

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from lnbits.extensions.watchonly import watchonly_ext
from .crud import (
    create_watch_wallet,
    get_watch_wallet,
    get_watch_wallets,
    update_watch_wallet,
    delete_watch_wallet,
    get_fresh_address,
    get_addresses,
    create_mempool,
    update_mempool,
    get_mempool,
)

###################WALLETS#############################


@watchonly_ext.get("/api/v1/wallet")
@api_check_wallet_key("invoice")
async def api_wallets_retrieve():

    try:
        return (
            [wallet._asdict() for wallet in await get_watch_wallets(g.wallet.user)],
            HTTPStatus.OK,
        )
    except:
        return ""


@watchonly_ext.get("/api/v1/wallet/{wallet_id}")
@api_check_wallet_key("invoice")
async def api_wallet_retrieve(wallet_id):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        return {"message": "wallet does not exist"}, HTTPStatus.NOT_FOUND

    return wallet._asdict(), HTTPStatus.OK


@watchonly_ext.post("/api/v1/wallet")
@api_check_wallet_key("admin")
async def api_wallet_create_or_update(masterPub: str, Title: str, wallet_id=None):
    try:
        wallet = await create_watch_wallet(
            user=g.wallet.user, masterpub=masterPub, title=Title
        )
    except Exception as e:
        return {"message": str(e)}, HTTPStatus.BAD_REQUEST
    mempool = await get_mempool(g.wallet.user)
    if not mempool:
        create_mempool(user=g.wallet.user)
    return wallet._asdict(), HTTPStatus.CREATED


@watchonly_ext.delete("/api/v1/wallet/{wallet_id}")
@api_check_wallet_key("admin")
async def api_wallet_delete(wallet_id):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        return {"message": "Wallet link does not exist."}, HTTPStatus.NOT_FOUND

    await delete_watch_wallet(wallet_id)

    return {"deleted": "true"}, HTTPStatus.NO_CONTENT


#############################ADDRESSES##########################


@watchonly_ext.get("/api/v1/address/{wallet_id}")
@api_check_wallet_key("invoice")
async def api_fresh_address(wallet_id):
    await get_fresh_address(wallet_id)

    addresses = await get_addresses(wallet_id)

    return [address._asdict() for address in addresses], HTTPStatus.OK


@watchonly_ext.get("/api/v1/addresses/{wallet_id}")
@api_check_wallet_key("invoice")
async def api_get_addresses(wallet_id):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        return {"message": "wallet does not exist"}, HTTPStatus.NOT_FOUND

    addresses = await get_addresses(wallet_id)

    if not addresses:
        await get_fresh_address(wallet_id)
        addresses = await get_addresses(wallet_id)

    return [address._asdict() for address in addresses], HTTPStatus.OK


#############################MEMPOOL##########################


@watchonly_ext.put("/api/v1/mempool")
@api_check_wallet_key("admin")
async def api_update_mempool(endpoint: str):
    mempool = await update_mempool(user=g.wallet.user, **endpoint)
    return mempool._asdict(), HTTPStatus.OK


@watchonly_ext.get("/api/v1/mempool")
@api_check_wallet_key("admin")
async def api_get_mempool():
    mempool = await get_mempool(g.wallet.user)
    if not mempool:
        mempool = await create_mempool(user=g.wallet.user)
    return mempool._asdict(), HTTPStatus.OK
