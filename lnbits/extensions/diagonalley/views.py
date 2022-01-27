
from typing import List

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse  # type: ignore

from http import HTTPStatus
import json
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.diagonalley import diagonalley_ext

from .crud import (
    create_diagonalley_product,
    get_diagonalley_product,
    get_diagonalley_products,
    delete_diagonalley_product,
    create_diagonalley_order,
    get_diagonalley_order,
    get_diagonalley_orders,
    update_diagonalley_product,
)


@diagonalley_ext.get("/", response_class=HTMLResponse)
@validate_uuids(["usr"], required=True)
@check_user_exists(request: Request)
async def index():
    return await render_template("diagonalley/index.html", user=g.user)


@diagonalley_ext.get("/<stall_id>", response_class=HTMLResponse)
async def display(request: Request, stall_id):
    product = await get_diagonalley_products(stall_id)
    if not product:
        abort(HTTPStatus.NOT_FOUND, "Stall does not exist.")

    return await render_template(
        "diagonalley/stall.html",
        stall=json.dumps(
            [product._asdict() for product in await get_diagonalley_products(stall_id)]
        ),
    )
