from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import lnaddy_ext, lnurlp_renderer
from .crud import get_pay_link

templates = Jinja2Templates(directory="templates")


@lnaddy_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnurlp_renderer().TemplateResponse(
        "lnaddy/index.html", {"request": request, "user": user.dict()}
    )


@lnaddy_ext.get("/{link_id}", response_class=HTMLResponse)
async def display(request: Request, link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )
    ctx = {"request": request, "lnurl": link.lnurl(req=request)}
    return lnurlp_renderer().TemplateResponse("lnaddy/display.html", ctx)


@lnaddy_ext.get("/print/{link_id}", response_class=HTMLResponse)
async def print_qr(request: Request, link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )
    ctx = {"request": request, "lnurl": link.lnurl(req=request)}
    return lnurlp_renderer().TemplateResponse("lnaddy/print_qr.html", ctx)
