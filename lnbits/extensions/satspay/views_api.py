import json
from http import HTTPStatus

from fastapi.params import Depends
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet
from lnbits.decorators import (
    WalletTypeInfo,
    get_key_type,
    require_admin_key,
    require_invoice_key,
)
from lnbits.extensions.satspay import satspay_ext

from lnbits.settings import (
    LNBITS_ADMIN_EXTENSIONS,
    LNBITS_ADMIN_USERS,
)

from .crud import (
    check_address_balance,
    create_charge,
    delete_charge,
    get_charge,
    get_charges,
    get_theme,
    get_themes,
    delete_theme,
    save_theme,
    update_charge,
)
from .models import CreateCharge, SatsPayThemes
from .helpers import call_webhook, public_charge

#############################CHARGES##########################


@satspay_ext.post("/api/v1/charge")
async def api_charge_create(
    data: CreateCharge, wallet: WalletTypeInfo = Depends(require_invoice_key)
):
    charge = await create_charge(user=wallet.wallet.user, data=data)
    return {
        **charge.dict(),
        **{"time_elapsed": charge.time_elapsed},
        **{"time_left": charge.time_left},
        **{"paid": charge.paid},
    }


@satspay_ext.put("/api/v1/charge/{charge_id}")
async def api_charge_update(
    data: CreateCharge,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    charge_id=None,
):
    charge = await update_charge(charge_id=charge_id, data=data)
    return charge.dict()


@satspay_ext.get("/api/v1/charges")
async def api_charges_retrieve(wallet: WalletTypeInfo = Depends(get_key_type)):
    try:
        return [
            {
                **charge.dict(),
                **{"time_elapsed": charge.time_elapsed},
                **{"time_left": charge.time_left},
                **{"paid": charge.paid},
                **{"webhook_message": charge.config.webhook_message},
            }
            for charge in await get_charges(wallet.wallet.user)
        ]
    except:
        return ""


@satspay_ext.get("/api/v1/charge/{charge_id}")
async def api_charge_retrieve(
    charge_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    charge = await get_charge(charge_id)

    if not charge:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Charge does not exist."
        )

    return {
        **charge.dict(),
        **{"time_elapsed": charge.time_elapsed},
        **{"time_left": charge.time_left},
        **{"paid": charge.paid},
    }


@satspay_ext.delete("/api/v1/charge/{charge_id}")
async def api_charge_delete(charge_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    charge = await get_charge(charge_id)

    if not charge:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Charge does not exist."
        )

    await delete_charge(charge_id)
    return "", HTTPStatus.NO_CONTENT


#############################BALANCE##########################


@satspay_ext.get("/api/v1/charges/balance/{charge_ids}")
async def api_charges_balance(charge_ids):
    charge_id_list = charge_ids.split(",")
    charges = []
    for charge_id in charge_id_list:
        charge = await api_charge_balance(charge_id)
        charges.append(charge)
    return charges


@satspay_ext.get("/api/v1/charge/balance/{charge_id}")
async def api_charge_balance(charge_id):
    charge = await check_address_balance(charge_id)

    if not charge:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Charge does not exist."
        )

    if charge.must_call_webhook():
        resp = await call_webhook(charge)
        extra = {**charge.config.dict(), **resp}
        await update_charge(charge_id=charge.id, extra=json.dumps(extra))
