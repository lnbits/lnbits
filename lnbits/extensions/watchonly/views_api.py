from http import HTTPStatus

from fastapi import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.watchonly import watchonly_ext

from .crud import (
    create_mempool,
    create_watch_wallet,
    delete_watch_wallet,
    get_addresses,
    get_fresh_address,
    get_mempool,
    get_watch_wallet,
    get_watch_wallets,
    update_mempool,
)
from .models import CreateWallet

###################WALLETS#############################


@watchonly_ext.get("/api/v1/wallet")
async def api_wallets_retrieve(wallet: WalletTypeInfo = Depends(get_key_type)):

    try:
        return [wallet.dict() for wallet in await get_watch_wallets(wallet.wallet.user)]
    except:
        return ""


@watchonly_ext.get("/api/v1/wallet/{wallet_id}")
async def api_wallet_retrieve(
    wallet_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    w_wallet = await get_watch_wallet(wallet_id)

    if not w_wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    return w_wallet.dict()


@watchonly_ext.post("/api/v1/wallet")
async def api_wallet_create_or_update(
    data: CreateWallet, wallet_id=None, w: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        wallet = await create_watch_wallet(
            user=w.wallet.user, masterpub=data.masterpub, title=data.title
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

    mempool = await get_mempool(w.wallet.user)
    if not mempool:
        create_mempool(user=w.wallet.user)
    return wallet.dict()


@watchonly_ext.delete("/api/v1/wallet/{wallet_id}")
async def api_wallet_delete(wallet_id, w: WalletTypeInfo = Depends(require_admin_key)):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    await delete_watch_wallet(wallet_id)

    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


#############################ADDRESSES##########################


@watchonly_ext.get("/api/v1/address/{wallet_id}")
async def api_fresh_address(wallet_id, w: WalletTypeInfo = Depends(get_key_type)):
    address = await get_fresh_address(wallet_id)

    return [address.dict()]


@watchonly_ext.get("/api/v1/addresses/{wallet_id}")
async def api_get_addresses(wallet_id, w: WalletTypeInfo = Depends(get_key_type)):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    addresses = await get_addresses(wallet_id)

    if not addresses:
        await get_fresh_address(wallet_id)
        addresses = await get_addresses(wallet_id)

    return [address.dict() for address in addresses]


#############################MEMPOOL##########################


@watchonly_ext.put("/api/v1/mempool")
async def api_update_mempool(
    endpoint: str = Query(...), w: WalletTypeInfo = Depends(require_admin_key)
):
    mempool = await update_mempool(**{"endpoint": endpoint}, user=w.wallet.user)
    return mempool.dict()


@watchonly_ext.get("/api/v1/mempool")
async def api_get_mempool(w: WalletTypeInfo = Depends(require_admin_key)):
    mempool = await get_mempool(w.wallet.user)
    if not mempool:
        mempool = await create_mempool(user=w.wallet.user)
    return mempool.dict()
