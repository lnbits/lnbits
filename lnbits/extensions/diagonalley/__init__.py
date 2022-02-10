import asyncio

from fastapi import APIRouter, Request
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from http import HTTPStatus

from lnbits.settings import LNBITS_ADMIN_EXTENSIONS

diagonalley_ext: APIRouter = APIRouter(
    prefix="/diagonalley", tags=["diagonalley"]
)
db = Database("ext_diagonalley")
if 'nostradmin' not in LNBITS_ADMIN_EXTENSIONS:
    @diagonalley_ext.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return template_renderer().TemplateResponse(
                "error.html", {"request": request, "err": "Ask system admin to enable NostrAdmin!"}
            )
else:
    def diagonalley_renderer():
        return template_renderer(["lnbits/extensions/diagonalley/templates"])

    from .tasks import wait_for_paid_invoices
    from .views import *  # noqa
    from .views_api import *  # noqa


    def diagonalley_start():
        loop = asyncio.get_event_loop()
        loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))