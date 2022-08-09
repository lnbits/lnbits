from http import HTTPStatus
import httpx
import json


from fastapi import Query
from fastapi.params import Depends
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import tpos_ext
from .crud import create_tpos, delete_tpos, get_tpos, get_tposs, bech32_decode
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

@tpos_ext.post("/api/v1/tposs/{tpos_id}/invoices/{payment_request}/pay", status_code=HTTPStatus.OK)
async def api_tpos_pay_invoice(
    lnurl_data: PayLnurlWData, payment_request: str = None, tpos_id: str = None
):
    tpos = await get_tpos(tpos_id)

    lnurl = lnurl_data.lnurl.replace("lnurlw://", "").replace("lightning://", "").replace("LIGHTNING://", "").replace("lightning:", "").replace("LIGHTNING:", "")
    
    if(lnurl.lower().startswith("lnurl")):
        lnurl = bech32_decode(lnurl)
    else:
        lnurl = "https://" + lnurl

    print('lnurl')
    print(lnurl)

    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(lnurl, follow_redirects=True)
            if r.is_error:
                lnurl_response = json.loads(r.text)
            else:
                resp = json.loads(r.text)
                if resp["tag"] != "withdrawRequest":
                    lnurl_response = "Wrong type"
                else:
                    r2 = await client.get(
                        resp['callback'],
                        follow_redirects=True,
                        params={
                            "k1": resp['k1'],
                            "pr": payment_request,
                        }
                    )
                    if r2.is_error:
                        lnurl_response = "ERROR2!"
                    else:
                        resp2 = json.loads(r2.text)
                        lnurl_response = "OK"
        except (httpx.ConnectError, httpx.RequestError):
            print("BAD ERROR")
            lnurl_response = "Error!"

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
