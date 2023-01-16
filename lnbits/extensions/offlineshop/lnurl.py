from fastapi import Query
from lnurl import LnurlErrorResponse, LnurlPayActionResponse, LnurlPayResponse
from lnurl.models import ClearnetUrl, LightningInvoice, MilliSatoshi
from starlette.requests import Request

from lnbits.core.services import create_invoice
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

from . import offlineshop_ext
from .crud import get_item, get_shop


@offlineshop_ext.get("/lnurl/{item_id}", name="offlineshop.lnurl_response")
async def lnurl_response(req: Request, item_id: int = Query(...)) -> dict:
    item = await get_item(item_id)
    if not item:
        return {"status": "ERROR", "reason": "Item not found."}

    if not item.enabled:
        return {"status": "ERROR", "reason": "Item disabled."}

    price_msat = (
        await fiat_amount_as_satoshis(item.price, item.unit)
        if item.unit != "sat"
        else item.price
    ) * 1000

    resp = LnurlPayResponse(
        callback=ClearnetUrl(
            req.url_for("offlineshop.lnurl_callback", item_id=item.id), scheme="https"
        ),
        minSendable=MilliSatoshi(price_msat),
        maxSendable=MilliSatoshi(price_msat),
        metadata=await item.lnurlpay_metadata(),
    )

    return resp.dict()


@offlineshop_ext.get("/lnurl/cb/{item_id}", name="offlineshop.lnurl_callback")
async def lnurl_callback(request: Request, item_id: int):
    item = await get_item(item_id)
    if not item:
        return {"status": "ERROR", "reason": "Couldn't find item."}

    if item.unit == "sat":
        min = item.price * 1000
        max = item.price * 1000
    else:
        price = await fiat_amount_as_satoshis(item.price, item.unit)
        # allow some fluctuation (the fiat price may have changed between the calls)
        min = price * 995
        max = price * 1010

    amount_received = int(request.query_params.get("amount") or 0)
    if amount_received < min:
        return LnurlErrorResponse(
            reason=f"Amount {amount_received} is smaller than minimum {min}."
        ).dict()
    elif amount_received > max:
        return LnurlErrorResponse(
            reason=f"Amount {amount_received} is greater than maximum {max}."
        ).dict()

    shop = await get_shop(item.shop)
    assert shop

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=shop.wallet,
            amount=int(amount_received / 1000),
            memo=item.name,
            unhashed_description=(await item.lnurlpay_metadata()).encode(),
            extra={"tag": "offlineshop", "item": item.id},
        )
    except Exception as exc:
        return LnurlErrorResponse(reason=str(exc)).dict()

    if shop.method:
        success_action = item.success_action(shop, payment_hash, request)
        assert success_action
        resp = LnurlPayActionResponse(
            pr=LightningInvoice(payment_request),
            successAction=success_action,
            routes=[],
        )

        return resp.dict()
