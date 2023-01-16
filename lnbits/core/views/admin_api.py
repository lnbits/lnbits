from http import HTTPStatus
from typing import Optional

from fastapi import Body, Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.core.services import update_cached_settings, update_wallet_balance
from lnbits.decorators import check_admin, check_super_user
from lnbits.server import server_restart
from lnbits.settings import AdminSettings, EditableSettings

from .. import core_app
from ..crud import delete_admin_settings, get_admin_settings, update_admin_settings


@core_app.get("/admin/api/v1/settings/")
async def api_get_settings(
    user: User = Depends(check_admin),
) -> Optional[AdminSettings]:
    admin_settings = await get_admin_settings(user.super_user)
    return admin_settings


@core_app.put(
    "/admin/api/v1/settings/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_update_settings(data: EditableSettings):
    await update_admin_settings(data)
    update_cached_settings(dict(data))
    return {"status": "Success"}


@core_app.delete(
    "/admin/api/v1/settings/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_delete_settings() -> None:
    await delete_admin_settings()
    server_restart.set()


@core_app.get(
    "/admin/api/v1/restart/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_restart_server() -> dict[str, str]:
    server_restart.set()
    return {"status": "Success"}


@core_app.put(
    "/admin/api/v1/topup/",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_super_user)],
)
async def api_topup_balance(
    id: str = Body(...), amount: int = Body(...)
) -> dict[str, str]:
    try:
        await get_wallet(id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="wallet does not exist."
        )

    await update_wallet_balance(wallet_id=id, amount=int(amount))

    return {"status": "Success"}
