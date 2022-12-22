from base64 import urlsafe_b64encode
from http import HTTPStatus
from typing import List, Union
from uuid import uuid4

from fastapi import Request
from fastapi.param_functions import Body, Query
from fastapi.params import Depends
from loguru import logger
from secp256k1 import PrivateKey, PublicKey
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import (
    WalletTypeInfo,
    get_key_type,
    require_admin_key,
    require_invoice_key,
)

from ...helpers import urlsafe_short_hash
from . import db, shop_ext
from .crud import (
    create_shop_market,
    create_shop_market_stalls,
    create_shop_order,
    create_shop_order_details,
    create_shop_product,
    create_shop_stall,
    create_shop_zone,
    delete_shop_order,
    delete_shop_product,
    delete_shop_stall,
    delete_shop_zone,
    get_shop_chat_by_merchant,
    get_shop_chat_messages,
    get_shop_latest_chat_messages,
    get_shop_market,
    get_shop_market_stalls,
    get_shop_markets,
    get_shop_order,
    get_shop_order_details,
    get_shop_order_invoiceid,
    get_shop_orders,
    get_shop_product,
    get_shop_products,
    get_shop_stall,
    get_shop_stalls,
    get_shop_stalls_by_ids,
    get_shop_zone,
    get_shop_zones,
    set_shop_order_pubkey,
    update_shop_market,
    update_shop_product,
    update_shop_stall,
    update_shop_zone,
)
from .models import (
    CreateMarket,
    Orders,
    Products,
    Stalls,
    Zones,
    createOrder,
    createProduct,
    createStalls,
    createZones,
)

# from lnbits.db import open_ext_db


### Products
@shop_ext.get("/api/v1/products")
async def api_shop_products(
    wallet: WalletTypeInfo = Depends(require_invoice_key),
    all_stalls: bool = Query(False),
):
    wallet_ids = [wallet.wallet.id]

    if all_stalls:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    stalls = [stall.id for stall in await get_shop_stalls(wallet_ids)]

    if not stalls:
        return

    return [product.dict() for product in await get_shop_products(stalls)]


@shop_ext.post("/api/v1/products")
@shop_ext.put("/api/v1/products/{product_id}")
async def api_shop_product_create(
    data: createProduct,
    product_id=None,
    wallet: WalletTypeInfo = Depends(require_invoice_key),
):

    if product_id:
        product = await get_shop_product(product_id)
        if not product:
            return {"message": "Withdraw product does not exist."}

        stall = await get_shop_stall(stall_id=product.stall)
        if stall.wallet != wallet.wallet.id:
            return {"message": "Not your withdraw product."}

        product = await update_shop_product(product_id, **data.dict())
    else:
        product = await create_shop_product(data=data)

    return product.dict()


@shop_ext.delete("/api/v1/products/{product_id}")
async def api_shop_products_delete(
    product_id, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    product = await get_shop_product(product_id)

    if not product:
        return {"message": "Product does not exist."}

    stall = await get_shop_stall(product.stall)
    if stall.wallet != wallet.wallet.id:
        return {"message": "Not your Shop."}

    await delete_shop_product(product_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# # # Shippingzones


@shop_ext.get("/api/v1/zones")
async def api_shop_zones(wallet: WalletTypeInfo = Depends(get_key_type)):

    return await get_shop_zones(wallet.wallet.user)


@shop_ext.post("/api/v1/zones")
async def api_shop_zone_create(
    data: createZones, wallet: WalletTypeInfo = Depends(get_key_type)
):
    zone = await create_shop_zone(user=wallet.wallet.user, data=data)
    return zone.dict()


@shop_ext.post("/api/v1/zones/{zone_id}")
async def api_shop_zone_update(
    data: createZones,
    zone_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    zone = await get_shop_zone(zone_id)
    if not zone:
        return {"message": "Zone does not exist."}
    if zone.user != wallet.wallet.user:
        return {"message": "Not your record."}
    zone = await update_shop_zone(zone_id, **data.dict())
    return zone


@shop_ext.delete("/api/v1/zones/{zone_id}")
async def api_shop_zone_delete(
    zone_id, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    zone = await get_shop_zone(zone_id)

    if not zone:
        return {"message": "zone does not exist."}

    if zone.user != wallet.wallet.user:
        return {"message": "Not your zone."}

    await delete_shop_zone(zone_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# # # Stalls


@shop_ext.get("/api/v1/stalls")
async def api_shop_stalls(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [stall.dict() for stall in await get_shop_stalls(wallet_ids)]


@shop_ext.post("/api/v1/stalls")
@shop_ext.put("/api/v1/stalls/{stall_id}")
async def api_shop_stall_create(
    data: createStalls,
    stall_id: str = None,
    wallet: WalletTypeInfo = Depends(require_invoice_key),
):

    if stall_id:
        stall = await get_shop_stall(stall_id)
        if not stall:
            return {"message": "Withdraw stall does not exist."}

        if stall.wallet != wallet.wallet.id:
            return {"message": "Not your withdraw stall."}

        stall = await update_shop_stall(stall_id, **data.dict())
    else:
        stall = await create_shop_stall(data=data)

    return stall.dict()


@shop_ext.delete("/api/v1/stalls/{stall_id}")
async def api_shop_stall_delete(
    stall_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    stall = await get_shop_stall(stall_id)

    if not stall:
        return {"message": "Stall does not exist."}

    if stall.wallet != wallet.wallet.id:
        return {"message": "Not your Stall."}

    await delete_shop_stall(stall_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


###Orders


@shop_ext.get("/api/v1/orders")
async def api_shop_orders(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    orders = await get_shop_orders(wallet_ids)
    orders_with_details = []
    for order in orders:
        order = order.dict()
        order["details"] = await get_shop_order_details(order["id"])
        orders_with_details.append(order)
    try:
        return orders_with_details  # [order for order in orders]
        # return [order.dict() for order in await get_shop_orders(wallet_ids)]
    except:
        return {"message": "We could not retrieve the orders."}


@shop_ext.get("/api/v1/orders/{order_id}")
async def api_shop_order_by_id(order_id: str):
    order = (await get_shop_order(order_id)).dict()
    order["details"] = await get_shop_order_details(order_id)

    return order


@shop_ext.post("/api/v1/orders")
async def api_shop_order_create(data: createOrder):
    ref = urlsafe_short_hash()

    payment_hash, payment_request = await create_invoice(
        wallet_id=data.wallet,
        amount=data.total,
        memo=f"New order on Diagon alley",
        extra={
            "tag": "shop",
            "reference": ref,
        },
    )
    order_id = await create_shop_order(invoiceid=payment_hash, data=data)
    logger.debug(f"ORDER ID {order_id}")
    logger.debug(f"PRODUCTS {data.products}")
    await create_shop_order_details(order_id=order_id, data=data.products)
    return {
        "payment_hash": payment_hash,
        "payment_request": payment_request,
        "order_reference": ref,
    }


@shop_ext.get("/api/v1/orders/payments/{payment_hash}")
async def api_shop_check_payment(payment_hash: str):
    order = await get_shop_order_invoiceid(payment_hash)
    if not order:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Order does not exist."
        )
    try:
        status = await api_payment(payment_hash)

    except Exception as exc:
        logger.error(exc)
        return {"paid": False}
    return status


@shop_ext.delete("/api/v1/orders/{order_id}")
async def api_shop_order_delete(
    order_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    order = await get_shop_order(order_id)

    if not order:
        return {"message": "Order does not exist."}

    if order.wallet != wallet.wallet.id:
        return {"message": "Not your Order."}

    await delete_shop_order(order_id)

    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


@shop_ext.get("/api/v1/orders/paid/{order_id}")
async def api_shop_order_paid(
    order_id, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    await db.execute(
        "UPDATE shop.orders SET paid = ? WHERE id = ?",
        (
            True,
            order_id,
        ),
    )
    return "", HTTPStatus.OK


@shop_ext.get("/api/v1/order/pubkey/{payment_hash}/{pubkey}")
async def api_shop_order_pubkey(payment_hash: str, pubkey: str):
    await set_shop_order_pubkey(payment_hash, pubkey)
    return "", HTTPStatus.OK


@shop_ext.get("/api/v1/orders/shipped/{order_id}")
async def api_shop_order_shipped(
    order_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    await db.execute(
        "UPDATE shop.orders SET shipped = ? WHERE id = ?",
        (
            True,
            order_id,
        ),
    )
    order = await db.fetchone("SELECT * FROM shop.orders WHERE id = ?", (order_id,))

    return order


###List products based on stall id


@shop_ext.get("/api/v1/stall/products/{stall_id}")
async def api_shop_stall_products(
    stall_id, wallet: WalletTypeInfo = Depends(get_key_type)
):

    rows = await db.fetchone("SELECT * FROM shop.stalls WHERE id = ?", (stall_id,))
    if not rows:
        return {"message": "Stall does not exist."}

    products = db.fetchone("SELECT * FROM shop.products WHERE wallet = ?", (rows[1],))
    if not products:
        return {"message": "No products"}

    return [products.dict() for products in await get_shop_products(rows[1])]


###Check a product has been shipped


@shop_ext.get("/api/v1/stall/checkshipped/{checking_id}")
async def api_shop_stall_checkshipped(
    checking_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    rows = await db.fetchone(
        "SELECT * FROM shop.orders WHERE invoiceid = ?", (checking_id,)
    )
    return {"shipped": rows["shipped"]}


##
# MARKETS
##


@shop_ext.get("/api/v1/markets")
async def api_shop_markets(wallet: WalletTypeInfo = Depends(get_key_type)):
    # await get_shop_market_stalls(market_id="FzpWnMyHQMcRppiGVua4eY")
    try:
        return [market.dict() for market in await get_shop_markets(wallet.wallet.user)]
    except:
        return {"message": "We could not retrieve the markets."}


@shop_ext.get("/api/v1/markets/{market_id}/stalls")
async def api_shop_market_stalls(market_id: str):
    stall_ids = await get_shop_market_stalls(market_id)
    return stall_ids


@shop_ext.post("/api/v1/markets")
@shop_ext.put("/api/v1/markets/{market_id}")
async def api_shop_stall_create(
    data: CreateMarket,
    market_id: str = None,
    wallet: WalletTypeInfo = Depends(require_invoice_key),
):
    if market_id:
        market = await get_shop_market(market_id)
        if not market:
            return {"message": "Market does not exist."}

        if market.usr != wallet.wallet.user:
            return {"message": "Not your market."}

        market = await update_shop_market(market_id, **data.dict())
    else:
        market = await create_shop_market(data=data)
        await create_shop_market_stalls(market_id=market.id, data=data.stalls)

    return market.dict()


## MESSAGES/CHAT


@shop_ext.get("/api/v1/chat/messages/merchant")
async def api_get_merchant_messages(
    orders: str = Query(...), wallet: WalletTypeInfo = Depends(require_admin_key)
):
    return [msg.dict() for msg in await get_shop_chat_by_merchant(orders.split(","))]


@shop_ext.get("/api/v1/chat/messages/{room_name}")
async def api_get_latest_chat_msg(room_name: str, all_messages: bool = Query(False)):
    if all_messages:
        messages = await get_shop_chat_messages(room_name)
    else:
        messages = await get_shop_latest_chat_messages(room_name)

    return messages
