import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_tpos")

tpos_ext: APIRouter = APIRouter(prefix="/tpos", tags=["TPoS"])

tpos_static_files = [
    {
        "path": "/tpos/static",
        "app": StaticFiles(directory="lnbits/extensions/tpos/static"),
        "name": "tpos_static",
    }
]


def tpos_renderer():
    return template_renderer(["lnbits/extensions/tpos/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def tpos_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
