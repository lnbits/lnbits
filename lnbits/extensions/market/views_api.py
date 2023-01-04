from base64 import urlsafe_b64encode
from http import HTTPStatus
from typing import List, Union
from uuid import uuid4

from fastapi import Body, Depends, Query, Request
from loguru import logger
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
from lnbits.helpers import urlsafe_short_hash
from lnbits.utils.exchange_rates import currencies, get_fiat_rate_satoshis

from . import db, market_ext
from .crud import (
    create_market_market,
    create_market_market_stalls,
    create_market_order,
    create_market_order_details,
    create_market_product,
    create_market_settings,
    create_market_stall,
    create_market_zone,
    delete_market_order,
    delete_market_product,
    delete_market_stall,
    delete_market_zone,
    get_market_chat_by_merchant,
    get_market_chat_messages,
    get_market_latest_chat_messages,
    get_market_market,
    get_market_market_stalls,
    get_market_markets,
    get_market_order,
    get_market_order_details,
    get_market_order_invoiceid,
    get_market_orders,
    get_market_product,
    get_market_products,
    get_market_settings,
    get_market_stall,
    get_market_stalls,
    get_market_stalls_by_ids,
    get_market_zone,
    get_market_zones,
    set_market_order_pubkey,
    set_market_settings,
    update_market_market,
    update_market_product,
    update_market_stall,
    update_market_zone,
)
from .models import (
    CreateMarket,
    CreateMarketStalls,
    Orders,
    Products,
    SetSettings,
    Stalls,
    Zones,
    createOrder,
    createProduct,
    createStalls,
    createZones,
)

# from lnbits.db import open_ext_db


### Products
@market_ext.get("/api/v1/products")
async def api_market_products(
    wallet: WalletTypeInfo = Depends(require_invoice_key),
    all_stalls: bool = Query(False),
):
    wallet_ids = [wallet.wallet.id]

    if all_stalls:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    stalls = [stall.id for stall in await get_market_stalls(wallet_ids)]

    if not stalls:
        return

    return [product.dict() for product in await get_market_products(stalls)]


@market_ext.post("/api/v1/products")
@market_ext.put("/api/v1/products/{product_id}")
async def api_market_product_create(
    data: createProduct,
    product_id=None,
    wallet: WalletTypeInfo = Depends(require_invoice_key),
):
    # For fiat currencies,
    # we multiply by data.fiat_base_multiplier (usually 100) to save the value in cents.
    settings = await get_market_settings(user=wallet.wallet.user)
    assert settings

    stall = await get_market_stall(stall_id=data.stall)
    assert stall

    if stall.currency != "sat":
        data.price *= settings.fiat_base_multiplier

    if product_id:
        product = await get_market_product(product_id)
        if not product:
            return {"message": "Product does not exist."}

        # stall = await get_market_stall(stall_id=product.stall)
        if stall.wallet != wallet.wallet.id:
            return {"message": "Not your product."}

        product = await update_market_product(product_id, **data.dict())
    else:
        product = await create_market_product(data=data)
    assert product
    return product.dict()


@market_ext.delete("/api/v1/products/{product_id}")
async def api_market_products_delete(
    product_id, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    product = await get_market_product(product_id)

    if not product:
        return {"message": "Product does not exist."}

    stall = await get_market_stall(product.stall)
    assert stall

    if stall.wallet != wallet.wallet.id:
        return {"message": "Not your Market."}

    await delete_market_product(product_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# # # Shippingzones


@market_ext.get("/api/v1/zones")
async def api_market_zones(wallet: WalletTypeInfo = Depends(get_key_type)):

    return await get_market_zones(wallet.wallet.user)


@market_ext.post("/api/v1/zones")
async def api_market_zone_create(
    data: createZones, wallet: WalletTypeInfo = Depends(get_key_type)
):
    zone = await create_market_zone(user=wallet.wallet.user, data=data)
    return zone.dict()


@market_ext.post("/api/v1/zones/{zone_id}")
async def api_market_zone_update(
    data: createZones,
    zone_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    zone = await get_market_zone(zone_id)
    if not zone:
        return {"message": "Zone does not exist."}
    if zone.user != wallet.wallet.user:
        return {"message": "Not your record."}
    zone = await update_market_zone(zone_id, **data.dict())
    return zone


@market_ext.delete("/api/v1/zones/{zone_id}")
async def api_market_zone_delete(
    zone_id, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    zone = await get_market_zone(zone_id)

    if not zone:
        return {"message": "zone does not exist."}

    if zone.user != wallet.wallet.user:
        return {"message": "Not your zone."}

    await delete_market_zone(zone_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# # # Stalls


@market_ext.get("/api/v1/stalls")
async def api_market_stalls(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [stall.dict() for stall in await get_market_stalls(wallet_ids)]


@market_ext.post("/api/v1/stalls")
@market_ext.put("/api/v1/stalls/{stall_id}")
async def api_market_stall_create(
    data: createStalls,
    stall_id: str = None,
    wallet: WalletTypeInfo = Depends(require_invoice_key),
):

    if stall_id:
        stall = await get_market_stall(stall_id)
        if not stall:
            return {"message": "Withdraw stall does not exist."}

        if stall.wallet != wallet.wallet.id:
            return {"message": "Not your withdraw stall."}

        stall = await update_market_stall(stall_id, **data.dict())
    else:
        stall = await create_market_stall(data=data)
    assert stall
    return stall.dict()


@market_ext.delete("/api/v1/stalls/{stall_id}")
async def api_market_stall_delete(
    stall_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    stall = await get_market_stall(stall_id)

    if not stall:
        return {"message": "Stall does not exist."}

    if stall.wallet != wallet.wallet.id:
        return {"message": "Not your Stall."}

    await delete_market_stall(stall_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


###Orders


@market_ext.get("/api/v1/orders")
async def api_market_orders(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    orders = await get_market_orders(wallet_ids)
    if not orders:
        return
    orders_with_details = []
    for order in orders:
        _order = order.dict()
        _order["details"] = await get_market_order_details(_order["id"])
        orders_with_details.append(_order)
    try:
        return orders_with_details  # [order for order in orders]
        # return [order.dict() for order in await get_market_orders(wallet_ids)]
    except:
        return {"message": "We could not retrieve the orders."}


@market_ext.get("/api/v1/orders/{order_id}")
async def api_market_order_by_id(order_id: str):
    order = await get_market_order(order_id)
    assert order
    _order = order.dict()
    _order["details"] = await get_market_order_details(order_id)

    return _order


@market_ext.post("/api/v1/orders")
async def api_market_order_create(data: createOrder):
    ref = urlsafe_short_hash()

    payment_hash, payment_request = await create_invoice(
        wallet_id=data.wallet,
        amount=data.total,
        memo=f"New order on Market",
        extra={
            "tag": "market",
            "reference": ref,
        },
    )
    order_id = await create_market_order(invoiceid=payment_hash, data=data)
    logger.debug(f"ORDER ID {order_id}")
    logger.debug(f"PRODUCTS {data.products}")
    await create_market_order_details(order_id=order_id, data=data.products)
    return {
        "payment_hash": payment_hash,
        "payment_request": payment_request,
        "order_reference": ref,
    }


@market_ext.get("/api/v1/orders/payments/{payment_hash}")
async def api_market_check_payment(payment_hash: str):
    order = await get_market_order_invoiceid(payment_hash)
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


@market_ext.delete("/api/v1/orders/{order_id}")
async def api_market_order_delete(
    order_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    order = await get_market_order(order_id)

    if not order:
        return {"message": "Order does not exist."}

    if order.wallet != wallet.wallet.id:
        return {"message": "Not your Order."}

    await delete_market_order(order_id)

    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# @market_ext.get("/api/v1/orders/paid/{order_id}")
# async def api_market_order_paid(
#     order_id, wallet: WalletTypeInfo = Depends(require_admin_key)
# ):
#     await db.execute(
#         "UPDATE market.orders SET paid = ? WHERE id = ?",
#         (
#             True,
#             order_id,
#         ),
#     )
#     return "", HTTPStatus.OK


@market_ext.get("/api/v1/order/pubkey/{payment_hash}/{pubkey}")
async def api_market_order_pubkey(payment_hash: str, pubkey: str):
    await set_market_order_pubkey(payment_hash, pubkey)
    return "", HTTPStatus.OK


@market_ext.get("/api/v1/orders/shipped/{order_id}")
async def api_market_order_shipped(
    order_id, shipped: bool = Query(...), wallet: WalletTypeInfo = Depends(get_key_type)
):
    await db.execute(
        "UPDATE market.orders SET shipped = ? WHERE id = ?",
        (
            shipped,
            order_id,
        ),
    )
    order = await db.fetchone("SELECT * FROM market.orders WHERE id = ?", (order_id,))

    return order


###List products based on stall id


# @market_ext.get("/api/v1/stall/products/{stall_id}")
# async def api_market_stall_products(
#     stall_id, wallet: WalletTypeInfo = Depends(get_key_type)
# ):

#     rows = await db.fetchone("SELECT * FROM market.stalls WHERE id = ?", (stall_id,))
#     if not rows:
#         return {"message": "Stall does not exist."}

#     products = db.fetchone("SELECT * FROM market.products WHERE wallet = ?", (rows[1],))
#     if not products:
#         return {"message": "No products"}

#     return [products.dict() for products in await get_market_products(rows[1])]


###Check a product has been shipped


# @market_ext.get("/api/v1/stall/checkshipped/{checking_id}")
# async def api_market_stall_checkshipped(
#     checking_id, wallet: WalletTypeInfo = Depends(get_key_type)
# ):
#     rows = await db.fetchone(
#         "SELECT * FROM market.orders WHERE invoiceid = ?", (checking_id,)
#     )
#     return {"shipped": rows["shipped"]}


##
# MARKETS
##


@market_ext.get("/api/v1/markets")
async def api_market_markets(wallet: WalletTypeInfo = Depends(get_key_type)):
    # await get_market_market_stalls(market_id="FzpWnMyHQMcRppiGVua4eY")
    try:
        return [
            market.dict() for market in await get_market_markets(wallet.wallet.user)
        ]
    except:
        return {"message": "We could not retrieve the markets."}


@market_ext.get("/api/v1/markets/{market_id}/stalls")
async def api_market_market_stalls(market_id: str):
    stall_ids = await get_market_market_stalls(market_id)
    return stall_ids


@market_ext.post("/api/v1/markets")
@market_ext.put("/api/v1/markets/{market_id}")
async def api_market_market_create(
    data: CreateMarket,
    market_id: str = None,
    wallet: WalletTypeInfo = Depends(require_invoice_key),
):
    if market_id:
        market = await get_market_market(market_id)
        if not market:
            return {"message": "Market does not exist."}

        if market.usr != wallet.wallet.user:
            return {"message": "Not your market."}

        market = await update_market_market(market_id, data.name)
    else:
        market = await create_market_market(data=data)

    assert market
    await create_market_market_stalls(market_id=market.id, data=data.stalls)

    return market.dict()


## MESSAGES/CHAT


@market_ext.get("/api/v1/chat/messages/merchant")
async def api_get_merchant_messages(
    orders: str = Query(...), wallet: WalletTypeInfo = Depends(require_admin_key)
):
    return [msg.dict() for msg in await get_market_chat_by_merchant(orders.split(","))]


@market_ext.get("/api/v1/chat/messages/{room_name}")
async def api_get_latest_chat_msg(room_name: str, all_messages: bool = Query(False)):
    if all_messages:
        messages = await get_market_chat_messages(room_name)
    else:
        messages = await get_market_latest_chat_messages(room_name)

    return messages


@market_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return list(currencies.keys())


@market_ext.get("/api/v1/settings")
async def api_get_settings(wallet: WalletTypeInfo = Depends(require_admin_key)):
    user = wallet.wallet.user

    settings = await get_market_settings(user)

    return settings


@market_ext.post("/api/v1/settings")
@market_ext.put("/api/v1/settings/{usr}")
async def api_set_settings(
    data: SetSettings,
    usr: str = None,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    if usr:
        if usr != wallet.wallet.user:
            return {"message": "Not your Market."}

        settings = await get_market_settings(user=usr)
        assert settings

        if settings.user != wallet.wallet.user:
            return {"message": "Not your Market."}

        return await set_market_settings(usr, data)

    user = wallet.wallet.user

    return await create_market_settings(user, data)
