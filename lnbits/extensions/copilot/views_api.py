from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import copilot_ext
from .crud import (
    create_copilot,
    delete_copilot,
    get_copilot,
    get_copilots,
    update_copilot,
)
from .models import CreateCopilotData
from .views import updater

#######################COPILOT##########################


@copilot_ext.get("/api/v1/copilot")
async def api_copilots_retrieve(
    req: Request, wallet: WalletTypeInfo = Depends(get_key_type) #type: ignore
):
    wallet_user = wallet.wallet.user
    copilots = [copilot.dict() for copilot in await get_copilots(wallet_user)]
    try:
        return copilots
    except:
        raise HTTPException(status_code=HTTPStatus.NO_CONTENT, detail="No copilots")


@copilot_ext.get("/api/v1/copilot/{copilot_id}")
async def api_copilot_retrieve(
    req: Request,
    copilot_id: str = Query(None),
    wallet: WalletTypeInfo = Depends(get_key_type), #type: ignore
):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Copilot not found"
        )
    if not copilot.lnurl_toggle:
        return copilot.dict()
    return {**copilot.dict(), **{"lnurl": copilot.lnurl(req)}}


@copilot_ext.post("/api/v1/copilot")
@copilot_ext.put("/api/v1/copilot/{juke_id}")
async def api_copilot_create_or_update(
    data: CreateCopilotData,
    copilot_id: str = Query(None),
    wallet: WalletTypeInfo = Depends(require_admin_key),  #type: ignore
):
    data.user = wallet.wallet.user
    data.wallet = wallet.wallet.id
    if copilot_id:
        copilot = await update_copilot(data, copilot_id=copilot_id)
    else:
        copilot = await create_copilot(data, inkey=wallet.wallet.inkey)
    return copilot


@copilot_ext.delete("/api/v1/copilot/{copilot_id}")
async def api_copilot_delete(
    copilot_id: str = Query(None),
    wallet: WalletTypeInfo = Depends(require_admin_key) #type: ignore
):
    copilot = await get_copilot(copilot_id)

    if not copilot:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Copilot does not exist"
        )

    await delete_copilot(copilot_id)

    return "", HTTPStatus.NO_CONTENT


@copilot_ext.get("/api/v1/copilot/ws/{copilot_id}/{comment}/{data}")
async def api_copilot_ws_relay(
    copilot_id: str = Query(None), comment: str = Query(None), data: str = Query(None)
):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Copilot does not exist"
        )
    try:
        await updater(copilot_id, data, comment)
    except:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your copilot")
    return ""
