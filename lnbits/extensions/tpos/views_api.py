from http import HTTPStatus

import httpx
from fastapi import Query
from fastapi.params import Depends
from lnurl import decode as decode_lnurl
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import tpos_ext
from .crud import create_tpos, delete_tpos, get_tpos, get_tposs
from .models import CreateTposData, PayLnurlWData


@tpos_ext.get("/api/v1/tposs", status_code=HTTPStatus.OK)
async def api_tposs(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [tpos.dict() for tpos in await get_tposs(wallet_ids)]


@tpos_ext.post("/api/v1/tposs", status_code=HTTPStatus.CREATED)
async def api_tpos_create(
    data: CreateTposData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    tpos = await create_tpos(wallet_id=wallet.wallet.id, data=data)
    return tpos.dict()


@tpos_ext.delete("/api/v1/tposs/{tpos_id}")
async def api_tpos_delete(
    tpos_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    if tpos.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your TPoS.")

    await delete_tpos(tpos_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


@tpos_ext.post("/api/v1/tposs/{tpos_id}/invoices", status_code=HTTPStatus.CREATED)
async def api_tpos_create_invoice(
    amount: int = Query(..., ge=1), tipAmount: int = None, tpos_id: str = None
):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    if tipAmount:
        amount += tipAmount

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=tpos.wallet,
            amount=amount,
            memo=f"{tpos.name}",
            extra={"tag": "tpos", "tipAmount": tipAmount, "tposId": tpos_id},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@tpos_ext.post(
    "/api/v1/tposs/{tpos_id}/invoices/{payment_request}/pay", status_code=HTTPStatus.OK
)
async def api_tpos_pay_invoice(
    lnurl_data: PayLnurlWData, payment_request: str = None, tpos_id: str = None
):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    lnurl = (
        lnurl_data.lnurl.replace("lnurlw://", "")
        .replace("lightning://", "")
        .replace("LIGHTNING://", "")
        .replace("lightning:", "")
        .replace("LIGHTNING:", "")
    )

    if lnurl.lower().startswith("lnurl"):
        lnurl = decode_lnurl(lnurl)
    else:
        lnurl = "https://" + lnurl

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(lnurl, follow_redirects=True)
            if r.is_error:
                lnurl_response = {"success": False, "detail": "Error loading"}
            else:
                resp = r.json()
                if resp["tag"] != "withdrawRequest":
                    lnurl_response = {"success": False, "detail": "Wrong tag type"}
                else:
                    r2 = await client.get(
                        resp["callback"],
                        follow_redirects=True,
                        params={
                            "k1": resp["k1"],
                            "pr": payment_request,
                        },
                    )
                    resp2 = r2.json()
                    if r2.is_error:
                        lnurl_response = {
                            "success": False,
                            "detail": "Error loading callback",
                        }
                    elif resp2["status"] == "ERROR":
                        lnurl_response = {"success": False, "detail": resp2["reason"]}
                    else:
                        lnurl_response = {"success": True, "detail": resp2}
        except (httpx.ConnectError, httpx.RequestError):
            lnurl_response = {"success": False, "detail": "Unexpected error occurred"}

    return lnurl_response


@tpos_ext.get(
    "/api/v1/tposs/{tpos_id}/invoices/{payment_hash}", status_code=HTTPStatus.OK
)
async def api_tpos_check_invoice(tpos_id: str, payment_hash: str):
    tpos = await get_tpos(tpos_id)
    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )
    try:
        status = await api_payment(payment_hash)

    except Exception as exc:
        logger.error(exc)
        return {"paid": False}
    return status
