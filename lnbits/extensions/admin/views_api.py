from http import HTTPStatus

from fastapi import Body, Depends, Request
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import check_admin
from lnbits.extensions.admin import admin_ext
from lnbits.extensions.admin.models import UpdateSettings
from lnbits.requestvars import g
from lnbits.server import server_restart
from lnbits.settings import settings

from .crud import delete_settings, update_settings, update_wallet_balance


@admin_ext.get("/api/v1/restart/", status_code=HTTPStatus.OK)
async def api_restart_server(user: User = Depends(check_admin)):
    server_restart.set()
    return {"status": "Success"}


@admin_ext.put("/api/v1/topup/", status_code=HTTPStatus.OK)
async def api_update_balance(
    wallet_id, topup_amount: int, user: User = Depends(check_admin)
):
    try:
        wallet = await get_wallet(wallet_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="wallet does not exist."
        )

    await update_wallet_balance(wallet_id=wallet_id, amount=int(topup_amount))

    return {"status": "Success"}


@admin_ext.put("/api/v1/settings/", status_code=HTTPStatus.OK)
async def api_update_settings(
    user: User = Depends(check_admin),
    data: UpdateSettings = Body(...),
):
    settings = await update_settings(data)
    logger.debug(settings)
    return {"status": "Success", "settings": settings.dict()}


@admin_ext.delete("/api/v1/settings/", status_code=HTTPStatus.OK)
async def api_delete_settings(
    user: User = Depends(check_admin),
):
    await delete_settings()
    return {"status": "Success"}


@admin_ext.get("/api/v1/backup/", status_code=HTTPStatus.OK)
async def api_backup(user: User = Depends(check_admin)):
    return {"status": "not implemented"}
