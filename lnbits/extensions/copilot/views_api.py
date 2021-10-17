from fastapi import Request
import hashlib
from http import HTTPStatus
from starlette.exceptions import HTTPException

from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
import base64
from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice, check_invoice_status
import json
from typing import Optional
from fastapi.params import Depends
from fastapi.param_functions import Query
from .models import Copilots, CreateCopilotData
from lnbits.decorators import (
    WalletAdminKeyChecker,
    WalletInvoiceKeyChecker,
    api_validate_post_request,
    check_user_exists,
    WalletTypeInfo,
    get_key_type,
    api_validate_post_request,
)
from .views import updater
import httpx
from . import copilot_ext
from .crud import (
    create_copilot,
    update_copilot,
    get_copilot,
    get_copilots,
    delete_copilot,
)

#######################COPILOT##########################


@copilot_ext.get("/api/v1/copilot")
async def api_copilots_retrieve(
    req: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_user = wallet.wallet.user
    copilots = [copilot.dict() for copilot in await get_copilots(wallet_user)]
    try:
        return copilots
    except:
        raise HTTPException(status_code=HTTPStatus.NO_CONTENT, detail="No copilots")


@copilot_ext.get("/api/v1/copilot/{copilot_id}")
async def api_copilot_retrieve(
    copilot_id: str = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Copilot not found"
        )
    if not copilot.lnurl_toggle:
        return copilot.dict()
    return {**copilot.dict(), **{"lnurl": copilot.lnurl}}


@copilot_ext.post("/api/v1/copilot")
@copilot_ext.put("/api/v1/copilot/{juke_id}")
async def api_copilot_create_or_update(
    data: CreateCopilotData,
    copilot_id: str = Query(None),
    wallet: WalletTypeInfo = Depends(get_key_type),
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
    copilot_id: str = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
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
