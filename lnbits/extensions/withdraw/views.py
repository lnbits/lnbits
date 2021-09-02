from quart import g, abort, render_template
from http import HTTPStatus
import pyqrcode
from io import BytesIO
from lnbits.decorators import check_user_exists, validate_uuids

from . import withdraw_ext
from .crud import get_withdraw_link, chunks
from fastapi import FastAPI, Request, Response

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@withdraw_ext.get("/", status_code=HTTPStatus.OK)
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("withdraw/index.html", {"request":request,"user":g.user})


@withdraw_ext.get("/{link_id}", status_code=HTTPStatus.OK)
async def display(request: Request, link_id, response: Response):
    link = await get_withdraw_link(link_id, 0)
    if not link:
        response.status_code = HTTPStatus.NOT_FOUND
        return "Withdraw link does not exist." #probably here is where we should return the 404??
    return await templates.TemplateResponse("withdraw/display.html", {"request":request,"link":link, "unique":True})


@withdraw_ext.get("/img/{link_id}", status_code=HTTPStatus.OK)
async def img(request: Request, link_id, response: Response):
    link = await get_withdraw_link(link_id, 0)
    if not link:
        response.status_code = HTTPStatus.NOT_FOUND
        return "Withdraw link does not exist."
    qr = pyqrcode.create(link.lnurl)
    stream = BytesIO()
    qr.svg(stream, scale=3)
    return (
        stream.getvalue(),
        200,
        {
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@withdraw_ext.get("/print/{link_id}", status_code=HTTPStatus.OK)
async def print_qr(request: Request, link_id, response: Response):
    link = await get_withdraw_link(link_id)
    if not link:
        response.status_code = HTTPStatus.NOT_FOUND
        return "Withdraw link does not exist."
    if link.uses == 0:
        return await templates.TemplateResponse("withdraw/print_qr.html", {"request":request,link:link, unique:False})
    links = []
    count = 0
    for x in link.usescsv.split(","):
        linkk = await get_withdraw_link(link_id, count)
        if not linkk:
            response.status_code = HTTPStatus.NOT_FOUND
            return "Withdraw link does not exist."
        links.append(str(linkk.lnurl))
        count = count + 1
    page_link = list(chunks(links, 2))
    linked = list(chunks(page_link, 5))
    return await templates.TemplateResponse("withdraw/print_qr.html", {"request":request,"link":linked, "unique":True})
