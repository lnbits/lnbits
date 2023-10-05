from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, Depends
from starlette.exceptions import HTTPException

from lnbits.core.models import User
from lnbits.core.services import (
    get_balance_delta,
    update_cached_settings,
)
from lnbits.decorators import check_admin
from lnbits.settings import AdminSettings, UpdateSettings

from .. import core_app_extra
from ..crud import get_admin_settings, update_admin_settings

admin_router = APIRouter(
    prefix="/admin/api/v1",
    dependencies=[Depends(check_admin)],
)


@admin_router.get(
    "/audit/",
    name="Audit",
    description="show the current balance of the node and the LNbits database",
)
async def api_auditor():
    try:
        delta, node_balance, total_balance = await get_balance_delta()
        return {
            "delta_msats": int(delta),
            "node_balance_msats": int(node_balance),
            "lnbits_balance_msats": int(total_balance),
        }
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Could not audit balance.",
        )


@admin_router.get(
    "/settings/",
    response_model=Optional[AdminSettings],
)
async def api_get_settings(
    user: User = Depends(check_admin),
) -> Optional[AdminSettings]:
    admin_settings = await get_admin_settings(user.super_user)
    return admin_settings


@admin_router.put(
    "/settings/",
    status_code=HTTPStatus.OK,
)
async def api_update_settings(data: UpdateSettings, user: User = Depends(check_admin)):
    await update_admin_settings(data)
    admin_settings = await get_admin_settings(user.super_user)
    assert admin_settings, "Updated admin settings not found."
    update_cached_settings(admin_settings.dict())
    core_app_extra.register_new_ratelimiter()
    return {"status": "Success"}
