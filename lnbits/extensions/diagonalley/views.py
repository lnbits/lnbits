from http import HTTPStatus
from typing import List

from fastapi import Query, Request, WebSocket, WebSocketDisconnect
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists  # type: ignore
from lnbits.extensions.diagonalley import diagonalley_ext, diagonalley_renderer

from .crud import (
    get_diagonalley_market,
    get_diagonalley_market_stalls,
    get_diagonalley_order_details,
    get_diagonalley_products,
    get_diagonalley_stall,
    get_diagonalley_zone,
    get_diagonalley_zones,
    update_diagonalley_product_stock,
)

templates = Jinja2Templates(directory="templates")


@diagonalley_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return diagonalley_renderer().TemplateResponse(
        "diagonalley/index.html", {"request": request, "user": user.dict()}
    )

@diagonalley_ext.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, merch: str =  Query(...), order: str = Query(...)):
    stall = await get_diagonalley_stall(merch)
    orders = await get_diagonalley_order_details(order)

    logger.debug(f"ORDER: {orders}")
        
    return diagonalley_renderer().TemplateResponse(
        "diagonalley/chat.html",
        {
            "request": request,
            "stall": {"id": stall.id, "name": stall.name, "publickey": stall.publickey, "wallet": stall.wallet },
            "orders": [details.dict() for details in orders]
        },
    )


@diagonalley_ext.get("/{stall_id}", response_class=HTMLResponse)
async def display(request: Request, stall_id):
    stall = await get_diagonalley_stall(stall_id)
    products = await get_diagonalley_products(stall_id)
    zones = []
    for id in stall.shippingzones.split(","):
        z = await get_diagonalley_zone(id)
        z = z.dict()
        zones.append({"label": z["countries"], "cost": z["cost"], "value": z["id"]})

    if not stall:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Stall does not exist."
        )

    stall = stall.dict()
    del stall["privatekey"]
    stall["zones"] = zones

    return diagonalley_renderer().TemplateResponse(
        "diagonalley/stall.html",
        {
            "request": request,
            "stall": stall,
            "products": [product.dict() for product in products],
        },
    )


@diagonalley_ext.get("/market/{market_id}", response_class=HTMLResponse)
async def display(request: Request, market_id):
    market = await get_diagonalley_market(market_id)

    if not market:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Marketplace doesn't exist."
        )

    stalls = await get_diagonalley_market_stalls(market_id)
    stalls_ids = [stall.id for stall in stalls]
    products = [
        product.dict() for product in await get_diagonalley_products(stalls_ids)
    ]

    return diagonalley_renderer().TemplateResponse(
        "diagonalley/market.html",
        {
            "request": request,
            "market": market,
            "stalls": [stall.dict() for stall in stalls],
            "products": products,
        },
    )

##################WEBSOCKET ROUTES########################

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, order_id: str):
        await websocket.accept()
        websocket.id = order_id
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, order_id: str):
        for connection in self.active_connections:
            if connection.id == order_id:
                await connection.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


