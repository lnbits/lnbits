from quart import g, jsonify
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import offlineshop_ext
from .crud import (
    get_or_create_shop_by_wallet,
    set_wordlist,
    add_item,
    update_item,
    get_items,
    delete_item_from_shop,
)
from .models import ShopCounter


@offlineshop_ext.route("/api/v1/offlineshop", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_shop_from_wallet():
    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    items = await get_items(shop.id)

    try:
        return (
            jsonify(
                {
                    **shop._asdict(),
                    **{
                        "items": [item.values() for item in items],
                    },
                }
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify({"message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."}),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@offlineshop_ext.route("/api/v1/offlineshop/items", methods=["POST"])
@offlineshop_ext.route("/api/v1/offlineshop/items/<item_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "name": {"type": "string", "empty": False, "required": True},
        "description": {"type": "string", "empty": False, "required": True},
        "image": {"type": "string", "required": False, "nullable": True},
        "price": {"type": "number", "required": True},
        "unit": {"type": "string", "allowed": ["sat", "USD"], "required": True},
    }
)
async def api_add_or_update_item(item_id=None):
    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    if item_id == None:
        await add_item(
            shop.id,
            g.data["name"],
            g.data["description"],
            g.data.get("image"),
            g.data["price"],
            g.data["unit"],
        )
        return "", HTTPStatus.CREATED
    else:
        await update_item(
            shop.id,
            item_id,
            g.data["name"],
            g.data["description"],
            g.data.get("image"),
            g.data["price"],
            g.data["unit"],
        )
        return "", HTTPStatus.OK


@offlineshop_ext.route("/api/v1/offlineshop/items/<item_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_delete_item(item_id):
    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    await delete_item_from_shop(shop.id, item_id)
    return "", HTTPStatus.NO_CONTENT


@offlineshop_ext.route("/api/v1/offlineshop/wordlist", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "wordlist": {"type": "string", "empty": True, "nullable": True, "required": True},
    }
)
async def api_set_wordlist():
    wordlist = g.data["wordlist"].split("\n") if g.data["wordlist"] else None
    wordlist = [word.strip() for word in wordlist if word.strip()]

    shop = await get_or_create_shop_by_wallet(g.wallet.id)
    if not shop:
        return "", HTTPStatus.NOT_FOUND

    updated_shop = await set_wordlist(shop.id, "\n".join(wordlist))
    if not updated_shop:
        return "", HTTPStatus.NOT_FOUND

    ShopCounter.reset(updated_shop)
    return "", HTTPStatus.OK
