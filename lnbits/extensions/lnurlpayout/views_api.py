from http import HTTPStatus

from fastapi import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment, api_payments_decode
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import lnurlpayout_ext
from .crud import create_lnurlpayout, delete_lnurlpayout, get_lnurlpayout, get_lnurlpayouts, get_lnurlpayout_from_wallet
from .models import lnurlpayout, CreateLnurlPayoutData


@lnurlpayout_ext.get("/api/v1/lnurlpayouts", status_code=HTTPStatus.OK)
async def api_lnurlpayouts(
    all_wallets: bool = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [lnurlpayout.dict() for lnurlpayout in await get_lnurlpayouts(wallet_ids)]


@lnurlpayout_ext.post("/api/v1/lnurlpayouts", status_code=HTTPStatus.CREATED)
async def api_lnurlpayout_create(
    data: CreateLnurlPayoutData, wallet: WalletTypeInfo = Depends(get_key_type)
):  
    print(await get_lnurlpayout_from_wallet(wallet.wallet.id))
    if await get_lnurlpayout_from_wallet(wallet.wallet.id):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Wallet already has lnurlpayout set")
        return
    url = await api_payments_decode({"data": data.lnurlpay})
    if "domain" not in url:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="LNURL could not be decoded")
        return
    if str(url["domain"])[0:4] != "http":
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not valid LNURL")
        return
    lnurlpayout = await create_lnurlpayout(wallet_id=wallet.wallet.id, data=data)
    if not lnurlpayout:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Failed to save LNURLPayout")
        return
    return lnurlpayout.dict()

@lnurlpayout_ext.delete("/api/v1/lnurlpayouts/{lnurlpayout_id}")
async def api_lnurlpayout_delete(
    lnurlpayout_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    lnurlpayout = await get_lnurlpayout(lnurlpayout_id)

    if not lnurlpayout:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurlpayout does not exist."
        )

    if lnurlpayout.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your lnurlpayout.")

    await delete_lnurlpayout(lnurlpayout_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)