import json
from http import HTTPStatus
from typing import List

from fastapi import (
    BackgroundTasks,
    Depends,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists  # type: ignore
from lnbits.extensions.market import market_ext, market_renderer
from lnbits.extensions.market.models import CreateChatMessage, SetSettings
from lnbits.extensions.market.notifier import Notifier

from .crud import (
    create_chat_message,
    create_market_settings,
    get_market_market,
    get_market_market_stalls,
    get_market_order_details,
    get_market_order_invoiceid,
    get_market_products,
    get_market_settings,
    get_market_stall,
    get_market_zone,
    get_market_zones,
    update_market_product_stock,
)

templates = Jinja2Templates(directory="templates")


@market_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    settings = await get_market_settings(user=user.id)

    if not settings:
        await create_market_settings(
            user=user.id, data=SetSettings(currency="sat", fiat_base_multiplier=1)
        )
        settings = await get_market_settings(user.id)
    assert settings
    return market_renderer().TemplateResponse(
        "market/index.html",
        {"request": request, "user": user.dict(), "currency": settings.currency},
    )


@market_ext.get("/stalls/{stall_id}", response_class=HTMLResponse)
async def stall(request: Request, stall_id):
    stall = await get_market_stall(stall_id)
    products = await get_market_products(stall_id)

    if not stall:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Stall does not exist."
        )

    zones = []
    for id in stall.shippingzones.split(","):
        zone = await get_market_zone(id)
        assert zone
        z = zone.dict()
        zones.append({"label": z["countries"], "cost": z["cost"], "value": z["id"]})

    _stall = stall.dict()

    _stall["zones"] = zones

    return market_renderer().TemplateResponse(
        "market/stall.html",
        {
            "request": request,
            "stall": _stall,
            "products": [product.dict() for product in products],
        },
    )


@market_ext.get("/market/{market_id}", response_class=HTMLResponse)
async def market(request: Request, market_id):
    market = await get_market_market(market_id)

    if not market:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Marketplace doesn't exist."
        )

    stalls = await get_market_market_stalls(market_id)
    stalls_ids = [stall.id for stall in stalls]
    products = [product.dict() for product in await get_market_products(stalls_ids)]

    return market_renderer().TemplateResponse(
        "market/market.html",
        {
            "request": request,
            "market": market,
            "stalls": [stall.dict() for stall in stalls],
            "products": products,
        },
    )


@market_ext.get("/order", response_class=HTMLResponse)
async def order_chat(
    request: Request,
    merch: str = Query(...),
    invoice_id: str = Query(...),
    keys: str = Query(None),
):
    stall = await get_market_stall(merch)
    assert stall
    order = await get_market_order_invoiceid(invoice_id)
    assert order
    _order = await get_market_order_details(order.id)
    products = await get_market_products(stall.id)
    assert products

    return market_renderer().TemplateResponse(
        "market/order.html",
        {
            "request": request,
            "stall": {
                "id": stall.id,
                "name": stall.name,
                "publickey": stall.publickey,
                "wallet": stall.wallet,
                "currency": stall.currency,
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


@market_ext.websocket("/ws/{room_name}")
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
