from http import HTTPStatus
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, Response
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl
from pydantic import BaseModel

from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.utils.exchange_rates import currencies

from . import offlineshop_ext
from .crud import (
    add_item,
    delete_item_from_shop,
    get_items,
    get_or_create_shop_by_wallet,
    set_method,
    update_item,
)
from .models import ShopCounter


@offlineshop_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return list(currencies.keys())


@offlineshop_ext.get("/api/v1/offlineshop")
async def api_shop_from_wallet(
    r: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    shop = await get_or_create_shop_by_wallet(wallet.wallet.id)
    assert shop
    items = await get_items(shop.id)
    try:
        return {
            **shop.dict(),
            **{"otp_key": shop.otp_key, "items": [item.values(r) for item in items]},
        }
    except LnurlInvalidUrl:
        raise HTTPException(
            status_code=HTTPStatus.UPGRADE_REQUIRED,
            detail="LNURLs need to be delivered over a publically accessible `https` domain or Tor.",
        )


class CreateItemsData(BaseModel):
    name: str
    description: str
    image: Optional[str]
    price: float
    unit: str
    fiat_base_multiplier: int = Query(100, ge=1)


@offlineshop_ext.post("/api/v1/offlineshop/items")
@offlineshop_ext.put("/api/v1/offlineshop/items/{item_id}")
async def api_add_or_update_item(
    data: CreateItemsData, item_id=None, wallet: WalletTypeInfo = Depends(get_key_type)
):
    shop = await get_or_create_shop_by_wallet(wallet.wallet.id)
    assert shop
    if data.image:
        image_is_url = data.image.startswith("https://") or data.image.startswith(
            "http://"
        )

        if not image_is_url:

            def size(b64string):
                return int((len(b64string) * 3) / 4 - b64string.count("=", -2))

            image_size = size(data.image) / 1024
            if image_size > 100:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Image size is too big, {int(image_size)}Kb. Max: 100kb, Compress the image at https://tinypng.com, or use an URL.",
                )
    if data.unit != "sat":
        data.price = data.price * 100
    if item_id is None:

        await add_item(
            shop.id,
            data.name,
            data.description,
            data.image,
            int(data.price),
            data.unit,
            data.fiat_base_multiplier,
        )
        return Response(status_code=HTTPStatus.CREATED)
    else:
        await update_item(
            shop.id,
            item_id,
            data.name,
            data.description,
            data.image,
            int(data.price),
            data.unit,
            data.fiat_base_multiplier,
        )


@offlineshop_ext.delete("/api/v1/offlineshop/items/{item_id}")
async def api_delete_item(item_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    shop = await get_or_create_shop_by_wallet(wallet.wallet.id)
    assert shop
    await delete_item_from_shop(shop.id, item_id)
    return "", HTTPStatus.NO_CONTENT


class CreateMethodData(BaseModel):
    method: str
    wordlist: Optional[str]


@offlineshop_ext.put("/api/v1/offlineshop/method")
async def api_set_method(
    data: CreateMethodData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    method = data.method

    wordlist = data.wordlist.split("\n") if data.wordlist else []
    wordlist = [word.strip() for word in wordlist if word.strip()]

    shop = await get_or_create_shop_by_wallet(wallet.wallet.id)
    if not shop:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    updated_shop = await set_method(shop.id, method, "\n".join(wordlist))
    if not updated_shop:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    ShopCounter.reset(updated_shop)
