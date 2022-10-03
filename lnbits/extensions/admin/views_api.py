from http import HTTPStatus

from fastapi import Body, Depends, Request
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import WalletTypeInfo, check_admin, require_admin_key
from lnbits.extensions.admin import admin_ext
from lnbits.extensions.admin.models import Funding, UpdateAdminSettings
from lnbits.helpers import removeEmptyString
from lnbits.requestvars import g
from lnbits.server import server_restart
from lnbits.settings import settings

from .crud import update_funding, update_settings, update_wallet_balance


@admin_ext.get("/api/v1/admin/restart/", status_code=HTTPStatus.OK)
async def api_restart_server(
    g: WalletTypeInfo = Depends(require_admin_key),  # type: ignore
):
    server_restart.set()
    return {"status": "Success"}


@admin_ext.get("/api/v1/admin/{wallet_id}/{topup_amount}", status_code=HTTPStatus.OK)
async def api_update_balance(
    wallet_id, topup_amount: int, g: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        wallet = await get_wallet(wallet_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not allowed: not an admin"
        )

    await update_wallet_balance(wallet_id=wallet_id, amount=int(topup_amount))

    return {"status": "Success"}


@admin_ext.post("/api/v1/admin/", status_code=HTTPStatus.OK)
async def api_update_admin(
    request: Request,
    data: UpdateAdminSettings = Body(...),
    w: WalletTypeInfo = Depends(require_admin_key),
):
    if not settings.user == w.wallet.user:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not allowed: not an admin"
        )
    updated = await update_admin(user=w.wallet.user, **data.dict())

    updated.admin_users = removeEmptyString(updated.admin_users.split(","))
    updated.allowed_users = removeEmptyString(updated.allowed_users.split(","))
    updated.admin_ext = removeEmptyString(updated.admin_ext.split(","))
    updated.disabled_ext = removeEmptyString(updated.disabled_ext.split(","))
    updated.theme = removeEmptyString(updated.theme.split(","))
    updated.ad_space = removeEmptyString(updated.ad_space.split(","))

    g().admin_conf = g().admin_conf.copy(update=updated.dict())

    return {"status": "Success"}


@admin_ext.post("/api/v1/admin/funding/", status_code=HTTPStatus.OK)
async def api_update_funding(
    request: Request,
    data: Funding = Body(...),
    w: WalletTypeInfo = Depends(require_admin_key),
):
    if not settings.user == w.wallet.user:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not allowed: not an admin"
        )

    funding = await update_funding(data=data)
    return funding
