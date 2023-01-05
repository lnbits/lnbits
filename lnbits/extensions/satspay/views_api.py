import json
from http import HTTPStatus

from fastapi import Depends, HTTPException, Query
from loguru import logger

from lnbits.decorators import (
    WalletTypeInfo,
    check_admin,
    get_key_type,
    require_admin_key,
    require_invoice_key,
)
from lnbits.extensions.satspay import satspay_ext

from .crud import (
    check_address_balance,
    create_charge,
    delete_charge,
    delete_theme,
    get_charge,
    get_charges,
    get_theme,
    get_themes,
    save_theme,
    update_charge,
)
from .helpers import call_webhook, public_charge
from .models import CreateCharge, SatsPayThemes


@satspay_ext.post("/api/v1/charge")
async def api_charge_create(
    data: CreateCharge, wallet: WalletTypeInfo = Depends(require_invoice_key)
):
    try:
        charge = await create_charge(user=wallet.wallet.user, data=data)
        assert charge
        return {
            **charge.dict(),
            **{"time_elapsed": charge.time_elapsed},
            **{"time_left": charge.time_left},
            **{"paid": charge.paid},
        }
    except Exception as ex:
        logger.debug(f"Satspay error: {str}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@satspay_ext.put(
    "/api/v1/charge/{charge_id}", dependencies=[Depends(require_admin_key)]
)
async def api_charge_update(
    data: CreateCharge,
    charge_id: str,
):
    charge = await update_charge(charge_id=charge_id, data=data)
    assert charge
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


@satspay_ext.get("/api/v1/charge/{charge_id}", dependencies=[Depends(get_key_type)])
async def api_charge_retrieve(charge_id: str):
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


@satspay_ext.delete("/api/v1/charge/{charge_id}", dependencies=[Depends(get_key_type)])
async def api_charge_delete(charge_id: str):
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

    return {**public_charge(charge)}


#############################THEMES##########################


@satspay_ext.post("/api/v1/themes", dependencies=[Depends(check_admin)])
@satspay_ext.post("/api/v1/themes/{css_id}", dependencies=[Depends(check_admin)])
async def api_themes_save(
    data: SatsPayThemes,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    css_id: str = Query(...),
):

    if css_id:
        theme = await save_theme(css_id=css_id, data=data)
    else:
        data.user = wallet.wallet.user
        theme = await save_theme(data=data, css_id="no_id")
    return theme


@satspay_ext.get("/api/v1/themes")
async def api_themes_retrieve(wallet: WalletTypeInfo = Depends(get_key_type)):
    try:
        return await get_themes(wallet.wallet.user)
    except HTTPException:
        logger.error("Error loading satspay themes")
        logger.error(HTTPException)
        return ""


@satspay_ext.delete("/api/v1/themes/{theme_id}", dependencies=[Depends(get_key_type)])
async def api_theme_delete(theme_id):
    theme = await get_theme(theme_id)

    if not theme:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Theme does not exist."
        )

    await delete_theme(theme_id)
    return "", HTTPStatus.NO_CONTENT
