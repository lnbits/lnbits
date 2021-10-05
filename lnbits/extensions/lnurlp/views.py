from http import HTTPStatus

from lnbits.decorators import check_user_exists

from . import lnurlp_ext, lnurlp_renderer
from .crud import get_pay_link
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates

from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User

templates = Jinja2Templates(directory="templates")

@lnurlp_ext.get("/", response_class=HTMLResponse)
# @validate_uuids(["usr"], required=True)
# @check_user_exists()
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnurlp_renderer().TemplateResponse("lnurlp/index.html", {"request": request, "user": user.dict()})


@lnurlp_ext.get("/{link_id}", response_class=HTMLResponse)
async def display(request: Request,link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Pay link does not exist."
        )
        # abort(HTTPStatus.NOT_FOUND, "Pay link does not exist.")

    return lnurlp_renderer().TemplateResponse("lnurlp/display.html", {"request": request, "link":link})


@lnurlp_ext.get("/print/{link_id}", response_class=HTMLResponse)
async def print_qr(request: Request,link_id):
    link = await get_pay_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Pay link does not exist."
        )
        # abort(HTTPStatus.NOT_FOUND, "Pay link does not exist.")

    return lnurlp_renderer().TemplateResponse("lnurlp/print_qr.html", {"request": request, "link":link})
