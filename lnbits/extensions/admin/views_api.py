from http import HTTPStatus

from fastapi import Body, Depends, Request
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.decorators import WalletTypeInfo, require_admin_key
from lnbits.extensions.admin import admin_ext
from lnbits.extensions.admin.models import Admin, UpdateAdminSettings

from .crud import get_admin, update_admin, update_wallet_balance


@admin_ext.get("/api/v1/admin/{wallet_id}/{topup_amount}", status_code=HTTPStatus.OK)
async def api_update_balance(wallet_id, topup_amount: int, g: WalletTypeInfo = Depends(require_admin_key)):
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
    g: WalletTypeInfo = Depends(require_admin_key)
    ):
    admin = await get_admin()
    print(data)
    if not admin.user == g.wallet.user:
        raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not allowed: not an admin"
            )
    updated = await update_admin(user=g.wallet.user, **data.dict())
    print(updated)
    return {"status": "Success"}
