from http import HTTPStatus
from loguru import logger

from fastapi import Body, Depends, Request
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import check_admin
from lnbits.extensions.admin import admin_ext
from lnbits.extensions.admin.models import UpdateSettings
from lnbits.requestvars import g
from lnbits.server import server_restart
from lnbits.settings import settings

from .crud import update_settings, update_wallet_balance


@admin_ext.get("/api/v1/admin/restart/", status_code=HTTPStatus.OK)
async def api_restart_server(
    user: User = Depends(check_admin)
):
    server_restart.set()
    return {"status": "Success"}


@admin_ext.put("/api/v1/admin/topup/", status_code=HTTPStatus.OK)
async def api_update_balance(
    wallet_id, topup_amount: int, user: User = Depends(check_admin)
):
    try:
        wallet = await get_wallet(wallet_id)
    except:
        raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="wallet: {wallet_id} does not exist."
        )

    await update_wallet_balance(wallet_id=wallet_id, amount=int(topup_amount))

    return {"status": "Success"}


@admin_ext.put("/api/v1/admin/", status_code=HTTPStatus.OK)
async def api_update_admin(
    request: Request,
    user: User = Depends(check_admin),
    data: UpdateSettings = Body(...),
):
    updated = await update_settings(data)
    g().settings = g().settings.copy(update=updated.dict())

    return {"status": "Success"}
