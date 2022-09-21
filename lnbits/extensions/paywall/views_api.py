from http import HTTPStatus

from fastapi import Depends, Query
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type

from . import paywall_ext
from .crud import create_paywall, delete_paywall, get_paywall, get_paywalls
from .models import CheckPaywallInvoice, CreatePaywall, CreatePaywallInvoice


@paywall_ext.get("/api/v1/paywalls")
async def api_paywalls(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [paywall.dict() for paywall in await get_paywalls(wallet_ids)]


@paywall_ext.post("/api/v1/paywalls")
async def api_paywall_create(
    data: CreatePaywall, wallet: WalletTypeInfo = Depends(get_key_type)
):
    paywall = await create_paywall(wallet_id=wallet.wallet.id, data=data)
    return paywall.dict()


@paywall_ext.delete("/api/v1/paywalls/{paywall_id}")
async def api_paywall_delete(
    paywall_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    paywall = await get_paywall(paywall_id)

    if not paywall:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Paywall does not exist."
        )

    if paywall.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your paywall."
        )

    await delete_paywall(paywall_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


@paywall_ext.post("/api/v1/paywalls/invoice/{paywall_id}")
async def api_paywall_create_invoice(
    data: CreatePaywallInvoice, paywall_id: str = Query(None)
):
    paywall = await get_paywall(paywall_id)
    if data.amount < paywall.amount:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Minimum amount is {paywall.amount} sat.",
        )
    try:
        amount = data.amount if data.amount > paywall.amount else paywall.amount
        payment_hash, payment_request = await create_invoice(
            wallet_id=paywall.wallet,
            amount=amount,
            memo=f"{paywall.memo}",
            extra={"tag": "paywall"},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@paywall_ext.post("/api/v1/paywalls/check_invoice/{paywall_id}")
async def api_paywal_check_invoice(
    data: CheckPaywallInvoice, paywall_id: str = Query(None)
):
    paywall = await get_paywall(paywall_id)
    payment_hash = data.payment_hash
    if not paywall:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Paywall does not exist."
        )
    try:
        status = await check_transaction_status(paywall.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return {"paid": False}

    if is_paid:
        wallet = await get_wallet(paywall.wallet)
        payment = await wallet.get_payment(payment_hash)
        await payment.set_pending(False)

        return {"paid": True, "url": paywall.url, "remembers": paywall.remembers}
    return {"paid": False}
