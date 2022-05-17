from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import scrub_ext, scrub_renderer
from .crud import get_pay_link

templates = Jinja2Templates(directory="templates")


@scrub_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return scrub_renderer().TemplateResponse(
        "scrub/index.html", {"request": request, "user": user.dict()}
    )


@scrub_ext.get("/{link_id}", response_class=HTMLResponse)
async def display(request: Request, link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Scrub link does not exist."
        )
    ctx = {"request": request, "lnurl": link.lnurl(req=request)}
    return scrub_renderer().TemplateResponse("scrub/display.html", ctx)


@scrub_ext.get("/print/{link_id}", response_class=HTMLResponse)
async def print_qr(request: Request, link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Scrub link does not exist."
        )
    ctx = {"request": request, "lnurl": link.lnurl(req=request)}
    return scrub_renderer().TemplateResponse("scrub/print_qr.html", ctx)
