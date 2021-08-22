from typing import Optional
from pydantic.main import BaseModel
from quart import g, jsonify
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.utils.exchange_rates import currencies

from . import offlineshop_ext
from .crud import (
    get_or_create_shop_by_wallet,
    set_method,
    add_item,
    update_item,
    get_items,
    delete_item_from_shop,
)
from .models import ShopCounter


@offlineshop_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return jsonify(list(currencies.keys()))


@offlineshop_ext.get("/api/v1/offlineshop")
@api_check_wallet_key("invoice")
async def api_shop_from_wallet():
    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    items = await get_items(shop.id)

    try:
        return (
                {
                    **shop._asdict(),
                    **{
                        "otp_key": shop.otp_key,
                        "items": [item.values() for item in items],
                    },
                },
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                },
            HTTPStatus.UPGRADE_REQUIRED,
        )

class CreateItemsData(BaseModel):
    name:  str
    description: str
    image:  Optional[str]
    price:  int 
    unit:  str 

@offlineshop_ext.post("/api/v1/offlineshop/items")
@offlineshop_ext.put("/api/v1/offlineshop/items/<item_id>")
@api_check_wallet_key("invoice")
async def api_add_or_update_item(data: CreateItemsData, item_id=None):
    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    if item_id == None:
        await add_item(
            shop.id,
            data.name,
            data.description,
            data.image,
            data.price,
            data.unit,
        )
        return "", HTTPStatus.CREATED
    else:
        await update_item(
            shop.id,
            item_id,
            data.name,
            data.description,
            data.image,
            data.price,
            data.unit,
        )
        return "", HTTPStatus.OK


@offlineshop_ext.delete("/api/v1/offlineshop/items/<item_id>")
@api_check_wallet_key("invoice")
async def api_delete_item(item_id):
    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    await delete_item_from_shop(shop.id, item_id)
    return "", HTTPStatus.NO_CONTENT


class CreateMethodData(BaseModel):
    method:  str
    wordlist: Optional[str]

@offlineshop_ext.put("/api/v1/offlineshop/method")
@api_check_wallet_key("invoice")
async def api_set_method(data: CreateMethodData):
    method = data.method

    wordlist = data.wordlist.split("\n") if data.wordlist else None
    wordlist = [word.strip() for word in wordlist if word.strip()]

    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    if not shop:
        return "", HTTPStatus.NOT_FOUND

    updated_shop = await set_method(shop.id, method, "\n".join(wordlist))
    if not updated_shop:
        return "", HTTPStatus.NOT_FOUND

    ShopCounter.reset(updated_shop)
    return "", HTTPStatus.OK
