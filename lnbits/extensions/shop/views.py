import json
from http import HTTPStatus
from typing import List

from fastapi import BackgroundTasks, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists  # type: ignore
from lnbits.extensions.shop import shop_ext, shop_renderer
from lnbits.extensions.shop.models import CreateChatMessage, SetSettings
from lnbits.extensions.shop.notifier import Notifier

from .crud import (
    create_chat_message,
    get_shop_market,
    get_shop_market_stalls,
    get_shop_order_details,
    get_shop_order_invoiceid,
    get_shop_products,
    get_shop_stall,
    get_shop_zone,
    get_shop_zones,
    update_shop_product_stock,
    get_shop_settings,
    create_shop_settings,
)

templates = Jinja2Templates(directory="templates")


@shop_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    settings = await get_shop_settings(user=user.id)

    if not settings:
        await create_shop_settings(
            user=user.id, data=SetSettings(currency="sat", fiat_base_multiplier=1)
        )
        settings = await get_shop_settings(user.id)
    return shop_renderer().TemplateResponse(
        "shop/index.html",
        {"request": request, "user": user.dict(), "currency": settings.currency},
    )


@shop_ext.get("/stalls/{stall_id}", response_class=HTMLResponse)
async def stall(request: Request, stall_id):
    stall = await get_shop_stall(stall_id)
    products = await get_shop_products(stall_id)
    zones = []
    for id in stall.shippingzones.split(","):
        z = await get_shop_zone(id)
        z = z.dict()
        zones.append({"label": z["countries"], "cost": z["cost"], "value": z["id"]})

    if not stall:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Stall does not exist."
        )

    stall = stall.dict()

    stall["zones"] = zones

    return shop_renderer().TemplateResponse(
        "shop/stall.html",
        {
            "request": request,
            "stall": stall,
            "products": [product.dict() for product in products],
        },
    )


@shop_ext.get("/market/{market_id}", response_class=HTMLResponse)
async def market(request: Request, market_id):
    market = await get_shop_market(market_id)

    if not market:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Marketplace doesn't exist."
        )

    stalls = await get_shop_market_stalls(market_id)
    stalls_ids = [stall.id for stall in stalls]
    products = [product.dict() for product in await get_shop_products(stalls_ids)]

    return shop_renderer().TemplateResponse(
        "shop/market.html",
        {
            "request": request,
            "market": market,
            "stalls": [stall.dict() for stall in stalls],
            "products": products,
        },
    )


@shop_ext.get("/order", response_class=HTMLResponse)
async def order_chat(
    request: Request,
    merch: str = Query(...),
    invoice_id: str = Query(...),
    keys: str = Query(None),
):
    stall = await get_shop_stall(merch)
    order = await get_shop_order_invoiceid(invoice_id)
    _order = await get_shop_order_details(order.id)
    products = await get_shop_products(stall.id)

    return shop_renderer().TemplateResponse(
        "shop/order.html",
        {
            "request": request,
            "stall": {
                "id": stall.id,
                "name": stall.name,
                "publickey": stall.publickey,
                "wallet": stall.wallet,
            },
            "publickey": keys.split(",")[0] if keys else None,
            "privatekey": keys.split(",")[1] if keys else None,
            "order_id": order.invoiceid,
            "order": [details.dict() for details in _order],
            "products": [product.dict() for product in products],
        },
    )


##################WEBSOCKET ROUTES########################

# Initialize Notifier:
notifier = Notifier()


@shop_ext.websocket("/ws/{room_name}")
async def websocket_endpoint(
    websocket: WebSocket, room_name: str, background_tasks: BackgroundTasks
):
    await notifier.connect(websocket, room_name)
    try:
        while True:
            data = await websocket.receive_text()
            d = json.loads(data)
            d["room_name"] = room_name

            room_members = (
                notifier.get_members(room_name)
                if notifier.get_members(room_name) is not None
                else []
            )

            if websocket not in room_members:
                print("Sender not in room member: Reconnecting...")
                await notifier.connect(websocket, room_name)
            await notifier._notify(data, room_name)

    except WebSocketDisconnect:
        notifier.remove(websocket, room_name)
