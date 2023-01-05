import asyncio

from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_market")

market_ext: APIRouter = APIRouter(prefix="/market", tags=["market"])

market_static_files = [
    {
        "path": "/market/static",
        "app": StaticFiles(directory="lnbits/extensions/market/static"),
        "name": "market_static",
    }
]

# if 'nostradmin' not in LNBITS_ADMIN_EXTENSIONS:
#     @market_ext.get("/", response_class=HTMLResponse)
#     async def index(request: Request):
#         return template_renderer().TemplateResponse(
#                 "error.html", {"request": request, "err": "Ask system admin to enable NostrAdmin!"}
#             )
# else:


def market_renderer():
    return template_renderer(["lnbits/extensions/market/templates"])
    # return template_renderer(["lnbits/extensions/market/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def market_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
