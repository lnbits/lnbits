import asyncio

from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_lnaddress")

lnaddress_ext: APIRouter = APIRouter(prefix="/lnaddress", tags=["lnaddress"])

lnaddress_static_files = [
    {
        "path": "/lnaddress/static",
        "app": StaticFiles(directory="lnbits/extensions/lnaddress/static"),
        "name": "lnaddress_static",
    }
]


def lnaddress_renderer():
    return template_renderer(["lnbits/extensions/lnaddress/templates"])


from .lnurl import *  # noqa
from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def lnaddress_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
