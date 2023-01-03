from datetime import datetime
from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import nostrnip5_ext, nostrnip5_renderer
from .crud import get_address, get_domain

templates = Jinja2Templates(directory="templates")


@nostrnip5_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return nostrnip5_renderer().TemplateResponse(
        "nostrnip5/index.html", {"request": request, "user": user.dict()}
    )


@nostrnip5_ext.get("/signup/{domain_id}", response_class=HTMLResponse)
async def signup(request: Request, domain_id: str):
    domain = await get_domain(domain_id)

    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
        )

    return nostrnip5_renderer().TemplateResponse(
        "nostrnip5/signup.html",
        {
            "request": request,
            "domain_id": domain_id,
            "domain": domain,
        },
    )


@nostrnip5_ext.get("/rotate/{domain_id}/{address_id}", response_class=HTMLResponse)
async def rotate(request: Request, domain_id: str, address_id: str):
    domain = await get_domain(domain_id)
    address = await get_address(domain_id, address_id)

    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
        )

    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    return nostrnip5_renderer().TemplateResponse(
        "nostrnip5/rotate.html",
        {
            "request": request,
            "domain_id": domain_id,
            "domain": domain,
            "address_id": address_id,
            "address": address,
        },
    )
