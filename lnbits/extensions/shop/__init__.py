import asyncio

from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_shop")

shop_ext: APIRouter = APIRouter(prefix="/shop", tags=["shop"])

shop_static_files = [
    {
        "path": "/shop/static",
        "app": StaticFiles(directory="lnbits/extensions/shop/static"),
        "name": "shop_static",
    }
]

# if 'nostradmin' not in LNBITS_ADMIN_EXTENSIONS:
#     @shop_ext.get("/", response_class=HTMLResponse)
#     async def index(request: Request):
#         return template_renderer().TemplateResponse(
#                 "error.html", {"request": request, "err": "Ask system admin to enable NostrAdmin!"}
#             )
# else:


def shop_renderer():
    return template_renderer(["lnbits/extensions/shop/templates"])
    # return template_renderer(["lnbits/extensions/shop/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def shop_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
