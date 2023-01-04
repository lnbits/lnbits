from http import HTTPStatus

from fastapi import Depends, Query
from lnurl import decode as lnurl_decode
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import lnurlpayout_ext
from .crud import (
    create_lnurlpayout,
    delete_lnurlpayout,
    get_lnurlpayout,
    get_lnurlpayout_from_wallet,
    get_lnurlpayouts,
)
from .models import CreateLnurlPayoutData

# from .tasks import on_invoice_paid


@lnurlpayout_ext.get("/api/v1/lnurlpayouts", status_code=HTTPStatus.OK)
async def api_lnurlpayouts(
    all_wallets: bool = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [lnurlpayout.dict() for lnurlpayout in await get_lnurlpayouts(wallet_ids)]


@lnurlpayout_ext.post("/api/v1/lnurlpayouts", status_code=HTTPStatus.CREATED)
async def api_lnurlpayout_create(
    data: CreateLnurlPayoutData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    if await get_lnurlpayout_from_wallet(wallet.wallet.id):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Wallet already has lnurlpayout set",
        )
    _ = lnurl_decode(data.lnurlpay)
    lnurlpayout = await create_lnurlpayout(
        wallet_id=wallet.wallet.id, admin_key=wallet.wallet.adminkey, data=data
    )

    if not lnurlpayout:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Failed to save LNURLPayout"
        )

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
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your lnurlpayout."
        )

    await delete_lnurlpayout(lnurlpayout_id)
    return "", HTTPStatus.NO_CONTENT


# TODO: what is this?!

# @lnurlpayout_ext.get("/api/v1/lnurlpayouts/{lnurlpayout_id}", status_code=HTTPStatus.OK)
# async def api_lnurlpayout_check(
#     lnurlpayout_id: str, wallet: WalletTypeInfo = Depends(get_key_type)
# ):
#     lnurlpayout = await get_lnurlpayout(lnurlpayout_id)
#     ## THIS
#     mock_payment = Payment(
#         checking_id="mock",
#         pending=False,
#         amount=1,
#         fee=1,
#         time=0000,
#         bolt11="mock",
#         preimage="mock",
#         payment_hash="mock",
#         wallet_id=lnurlpayout.wallet,
#     )
#     ## INSTEAD OF THIS
#     # payments = await get_payments(
#     #     wallet_id=lnurlpayout.wallet, complete=True, pending=False, outgoing=True, incoming=True
#     # )

#     result = await on_invoice_paid(mock_payment)
#     return
