from http import HTTPStatus
from io import BytesIO

import pyqrcode
from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, StreamingResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import withdraw_ext, withdraw_renderer
from .crud import chunks, get_withdraw_link

templates = Jinja2Templates(directory="templates")


@withdraw_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return withdraw_renderer().TemplateResponse(
        "withdraw/index.html", {"request": request, "user": user.dict()}
    )


@withdraw_ext.get("/{link_id}", response_class=HTMLResponse)
async def display(request: Request, link_id):
    link = await get_withdraw_link(link_id, 0)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
        )
    return withdraw_renderer().TemplateResponse(
        "withdraw/display.html",
        {
            "request": request,
            "link": link.dict(),
            "lnurl": link.lnurl(req=request),
            "unique": True,
        },
    )


@withdraw_ext.get("/img/{link_id}", response_class=StreamingResponse)
async def img(request: Request, link_id):
    link = await get_withdraw_link(link_id, 0)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
        )
    qr = pyqrcode.create(link.lnurl(request))
    stream = BytesIO()
    qr.svg(stream, scale=3)
    stream.seek(0)

    async def _generator(stream: BytesIO):
        yield stream.getvalue()

    return StreamingResponse(
        _generator(stream),
        headers={
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@withdraw_ext.get("/print/{link_id}", response_class=HTMLResponse)
async def print_qr(request: Request, link_id):
    link = await get_withdraw_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
        )
        # response.status_code = HTTPStatus.NOT_FOUND
        # return "Withdraw link does not exist."

    if link.uses == 0:

        return withdraw_renderer().TemplateResponse(
            "withdraw/print_qr.html",
            {"request": request, "link": link.dict(), "unique": False},
        )
    links = []
    count = 0

    for x in link.usescsv.split(","):
        linkk = await get_withdraw_link(link_id, count)
        if not linkk:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
            )
        links.append(str(linkk.lnurl(request)))
        count = count + 1
    page_link = list(chunks(links, 2))
    linked = list(chunks(page_link, 5))

    return withdraw_renderer().TemplateResponse(
        "withdraw/print_qr.html", {"request": request, "link": linked, "unique": True}
    )

@withdraw_ext.get("/csv/{link_id}", response_class=HTMLResponse)
async def print_qr(request: Request, link_id):
    link = await get_withdraw_link(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
        )
        # response.status_code = HTTPStatus.NOT_FOUND
        # return "Withdraw link does not exist."

    if link.uses == 0:

        return withdraw_renderer().TemplateResponse(
            "withdraw/csv.html",
            {"request": request, "link": link.dict(), "unique": False},
        )
    links = []
    count = 0

    for x in link.usescsv.split(","):
        linkk = await get_withdraw_link(link_id, count)
        if not linkk:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
            )
        links.append(str(linkk.lnurl(request)))
        count = count + 1
    page_link = list(chunks(links, 2))
    linked = list(chunks(page_link, 5))

    return withdraw_renderer().TemplateResponse(
        "withdraw/csv.html", {"request": request, "link": linked, "unique": True}
    )