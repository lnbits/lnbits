from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import lnurlp_ext, lnurlp_renderer
from .crud import get_pay_link

templates = Jinja2Templates(directory="templates")


@lnurlp_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnurlp_renderer().TemplateResponse(
        "lnurlp/index.html", {"request": request, "user": user.dict()}
    )


@lnurlp_ext.get("/link/{link_id}", response_class=HTMLResponse)
async def display(request: Request, link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )
    ctx = {"request": request, "lnurl": link.lnurl(req=request)}
    return lnurlp_renderer().TemplateResponse("lnurlp/display.html", ctx)


@lnurlp_ext.get("/print/{link_id}", response_class=HTMLResponse)
async def print_qr(request: Request, link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )
    ctx = {"request": request, "lnurl": link.lnurl(req=request)}
    return lnurlp_renderer().TemplateResponse("lnurlp/print_qr.html", ctx)
