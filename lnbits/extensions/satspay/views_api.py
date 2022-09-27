from http import HTTPStatus

import httpx
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.decorators import (
    WalletTypeInfo,
    get_key_type,
    require_admin_key,
    require_invoice_key,
)
from lnbits.extensions.satspay import satspay_ext

from .crud import (
    check_address_balance,
    create_charge,
    delete_charge,
    get_charge,
    get_charges,
    update_charge,
)
from .models import CreateCharge

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
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


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

    if charge.paid and charge.webhook:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    charge.webhook,
                    json={
                        "id": charge.id,
                        "description": charge.description,
                        "onchainaddress": charge.onchainaddress,
                        "payment_request": charge.payment_request,
                        "payment_hash": charge.payment_hash,
                        "time": charge.time,
                        "amount": charge.amount,
                        "balance": charge.balance,
                        "paid": charge.paid,
                        "timestamp": charge.timestamp,
                        "completelink": charge.completelink,
                    },
                    timeout=40,
                )
            except AssertionError:
                charge.webhook = None
    return {
        **charge.dict(),
        **{"time_elapsed": charge.time_elapsed},
        **{"time_left": charge.time_left},
        **{"paid": charge.paid},
    }
