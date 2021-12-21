from datetime import datetime
from http import HTTPStatus

from fastapi.param_functions import Body
from fastapi.params import Depends, Query
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.crud import get_user
from lnbits.core.services import perform_lnurlauth, redeem_lnurl_withdraw
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.swap.etleneum import contract_call_method, get_contract_state
from lnbits.extensions.swap.models import (
    CreateRecurrent,
    CreateReserve,
    CreateSwapIn,
    CreateSwapOut,
    SwapIn,
    Txid,
)
from lnbits.lnurl import decode

from . import swap_ext
from .crud import (
    create_recurrent,
    create_swap_in,
    create_swapout,
    delete_recurrent,
    get_recurrent_swapout,
    get_recurrents,
    get_swap_in,
    get_swapins,
    get_swapouts,
    unique_recurrent_swapout,
    update_recurrent,
    update_swap_in,
)


# SWAP OUT
@swap_ext.get("/api/v1/out")
async def api_swap_outs(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [swap.dict() for swap in await get_swapouts(wallet_ids)]

@swap_ext.post("/api/v1/out")
async def api_swapout_create(
    data: CreateSwapOut,
    wallet: WalletTypeInfo = Depends(require_admin_key)
):
                
    swap_out = await create_swapout(data)
    return swap_out.dict()


## RECURRENT

@swap_ext.get("/api/v1/recurrent")
async def api_swap_outs(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [rec.dict() for rec in await get_recurrents(wallet_ids)]

@swap_ext.post("/api/v1/recurrent")
@swap_ext.put("/api/v1/recurrent/{swap_id}")
async def api_swapout_create_or_update_recurrent(
    data: CreateRecurrent,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    swap_id = None,
):
    if not swap_id:
        ## CHECK IF THERE'S ALREADY A RECURRENT SWAP
        ## ONLY ONE PER WALLET
        is_unique = await unique_recurrent_swapout(data.wallet)
        if is_unique > 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="This wallet already has a recurrent swap!"
            )
        recurrent = await create_recurrent(data=data)
        return recurrent.dict()
    else:
        obj = data.dict()
        if obj["onchainwallet"] and len(obj["onchainwallet"]) > 0:
            obj["onchainaddress"] = f"Watch-only wallet {obj['onchainwallet']}."
        
        recurrent = await update_recurrent(swap_id, **obj)
        return recurrent.dict()

@swap_ext.delete("/api/v1/recurrent/{swap_id}")
async def api_delete_recurrent_swapout(swap_id, g: WalletTypeInfo = Depends(require_admin_key)):
    swap = await get_recurrent_swapout(swap_id)
    if not swap:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Recurrent swap does not exist."
        )
    if swap.wallet != g.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your Swap."
        )

    await delete_recurrent(swap_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


## SWAP IN
@swap_ext.get("/api/v1/in")
async def api_swap_ins(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [swap.dict() for swap in await get_swapins(wallet_ids)]

@swap_ext.get("/api/v1/offers")
async def api_get_etleneum_offers():
    offers = await get_contract_state()
    
    return offers["value"]

@swap_ext.get("/api/v1/auth/{lnurl}")
async def api_perform_etleneum_auth(lnurl, wallet: WalletTypeInfo = Depends(require_admin_key)):
    auth = await perform_lnurlauth(decode(lnurl), wallet=wallet)
    return auth

@swap_ext.post("/api/v1/reserve/{session_id}")
async def api_perform_reserve_offers(session_id, data: CreateReserve, wallet: WalletTypeInfo = Depends(require_admin_key)):
    addresses = data.dict().get("addresses")
    call = await contract_call_method(
        "reserve",
        {"addresses": [addr["addr"] for addr in addresses]},
        data.fees,
        session = session_id         
    )
    resp = call["value"]
    return {"id": resp["id"], "invoice": resp["invoice"]}

@swap_ext.post("/api/v1/in")
async def api_swapin_create(data: CreateSwapIn, wallet: WalletTypeInfo = Depends(require_admin_key)):
    
    swap = await create_swap_in(data=data)
    return swap.dict()

@swap_ext.put("/api/v1/in/{swap_id}")
async def api_update_swap_in(swap_id, data: Txid, wallet: WalletTypeInfo = Depends(require_admin_key)):
    
    updated_swap = await update_swap_in(swap_id, **data.dict())
    return updated_swap.dict()

@swap_ext.get("/api/v1/in/{swap_id}/{txid}")
async def api_perform_txsent(swap_id, txid, wallet: WalletTypeInfo = Depends(require_admin_key)):
    swap = await get_swap_in(swap_id)
    if not swap:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Swap does not exist."
            )
    call = await contract_call_method(
        "txsent",
        {"txid": txid},
        0,
        swap.session_id
    )
    if not call:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Problem with etleneum!"
        )
    
    if not call["ok"]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Problem with etleneum: "
            + call["error"],
        )
    
    resp = call["value"]
    return {"id": resp["id"], "invoice": resp["invoice"]}

@swap_ext.get("/api/v1/checkbalance/{lnurl_w}")
async def check_account_widthraw(lnurl_w, request: Request, wallet: WalletTypeInfo = Depends(get_key_type)):
    swap_id = request.query_params['id']
    await redeem_lnurl_withdraw(
        wallet_id=wallet.wallet.id,
        lnurl_request=lnurl_w,
        memo=swap_id,
        extra={"tag": f"swapin"},
        )


@swap_ext.get("/api/v1/bump")
async def api_perform_bump(wallet: WalletTypeInfo = Depends(get_key_type)):
    call = await contract_call_method(
        "bump",
        {},
        0,
    )
    if not call["ok"]:        
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Problem with etleneum: "
            + call["error"],
        )
    
    resp = call["value"]
    return {"id": resp["id"], "invoice": resp["invoice"]}
