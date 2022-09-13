from http import HTTPStatus

from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type

from ..satspay.crud import create_charge
from . import tipjar_ext
from .crud import (
    create_tip,
    create_tipjar,
    delete_tip,
    delete_tipjar,
    get_tip,
    get_tipjar,
    get_tipjars,
    get_tips,
    update_tip,
    update_tipjar,
)
from .helpers import get_charge_details
from .models import CreateCharge, createTipJar, createTips


@tipjar_ext.post("/api/v1/tipjars")
async def api_create_tipjar(data: createTipJar):
    """Create a tipjar, which holds data about how/where to post tips"""
    try:
        tipjar = await create_tipjar(data)
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return tipjar.dict()


async def user_from_wallet(wallet: WalletTypeInfo = Depends(get_key_type)):
    return wallet.wallet.user


@tipjar_ext.post("/api/v1/tips")
async def api_create_tip(data: createTips):
    """Take data from tip form and return satspay charge"""
    sats = data.sats
    message = data.message
    if not message:
        message = "No message"
    tipjar_id = data.tipjar
    tipjar = await get_tipjar(tipjar_id)

    webhook = tipjar.webhook
    charge_details = await get_charge_details(tipjar.id)
    name = data.name
    # Ensure that description string can be split reliably
    name = name.replace('"', "''")
    if not name:
        name = "Anonymous"
    description = f"{name}: {message}"
    charge = await create_charge(
        user=charge_details["user"],
        data=CreateCharge(
            amount=sats,
            webhook=webhook,
            description=description,
            onchainwallet=charge_details["onchainwallet"],
            lnbitswallet=charge_details["lnbitswallet"],
            completelink=charge_details["completelink"],
            completelinktext=charge_details["completelinktext"],
            time=charge_details["time"],
        ),
    )

    await create_tip(
        id=charge.id,
        wallet=tipjar.wallet,
        message=message,
        name=name,
        sats=data.sats,
        tipjar=data.tipjar,
    )

    return {"redirect_url": f"/satspay/{charge.id}"}


@tipjar_ext.get("/api/v1/tipjars")
async def api_get_tipjars(wallet: WalletTypeInfo = Depends(get_key_type)):
    """Return list of all tipjars assigned to wallet with given invoice key"""
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    tipjars = []
    for wallet_id in wallet_ids:
        new_tipjars = await get_tipjars(wallet_id)
        tipjars += new_tipjars if new_tipjars else []
    return [tipjar.dict() for tipjar in tipjars] if tipjars else []


@tipjar_ext.get("/api/v1/tips")
async def api_get_tips(wallet: WalletTypeInfo = Depends(get_key_type)):
    """Return list of all tips assigned to wallet with given invoice key"""
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    tips = []
    for wallet_id in wallet_ids:
        new_tips = await get_tips(wallet_id)
        tips += new_tips if new_tips else []
    return [tip.dict() for tip in tips] if tips else []


@tipjar_ext.put("/api/v1/tips/{tip_id}")
async def api_update_tip(
    wallet: WalletTypeInfo = Depends(get_key_type), tip_id: str = Query(None)
):
    """Update a tip with the data given in the request"""
    if tip_id:
        tip = await get_tip(tip_id)

        if not tip:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Tip does not exist."
            )

        if tip.wallet != wallet.wallet.id:

            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your tip."
            )

        tip = await update_tip(tip_id, **g.data)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="No tip ID specified"
        )
    return tip.dict()


@tipjar_ext.put("/api/v1/tipjars/{tipjar_id}")
async def api_update_tipjar(
    wallet: WalletTypeInfo = Depends(get_key_type), tipjar_id: str = Query(None)
):
    """Update a tipjar with the data given in the request"""
    if tipjar_id:
        tipjar = await get_tipjar(tipjar_id)

        if not tipjar:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="TipJar does not exist."
            )

        if tipjar.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your tipjar."
            )

        tipjar = await update_tipjar(tipjar_id, **data)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="No tipjar ID specified"
        )
    return tipjar.dict()


@tipjar_ext.delete("/api/v1/tips/{tip_id}")
async def api_delete_tip(
    wallet: WalletTypeInfo = Depends(get_key_type), tip_id: str = Query(None)
):
    """Delete the tip with the given tip_id"""
    tip = await get_tip(tip_id)
    if not tip:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No tip with this ID!"
        )
    if tip.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this tip!",
        )
    await delete_tip(tip_id)

    return "", HTTPStatus.NO_CONTENT


@tipjar_ext.delete("/api/v1/tipjars/{tipjar_id}")
async def api_delete_tipjar(
    wallet: WalletTypeInfo = Depends(get_key_type), tipjar_id: str = Query(None)
):
    """Delete the tipjar with the given tipjar_id"""
    tipjar = await get_tipjar(tipjar_id)
    if not tipjar:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No tipjar with this ID!"
        )
    if tipjar.wallet != wallet.wallet.id:

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this tipjar!",
        )
    await delete_tipjar(tipjar_id)

    return "", HTTPStatus.NO_CONTENT
