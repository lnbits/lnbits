from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists  # type: ignore
from lnbits.extensions.diagonalley import diagonalley_ext, diagonalley_renderer

from .crud import get_diagonalley_products

templates = Jinja2Templates(directory="templates")


@diagonalley_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return diagonalley_renderer().TemplateResponse(
        "diagonalley/index.html", {"request": request, "user": user.dict()}
    )


@diagonalley_ext.get("/{stall_id}", response_class=HTMLResponse)
async def display(request: Request, stall_id):
    product = await get_diagonalley_products(stall_id)

    if not product:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Stall does not exist."
        )
    return diagonalley_renderer().TemplateResponse(
        "diagonalley/stall.html",
        {
            "stall": [
                product.dict() for product in await get_diagonalley_products(stall_id)
            ]
        },
    )
