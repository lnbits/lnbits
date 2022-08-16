import asyncio

from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_invoices")

invoices_static_files = [
    {
        "path": "/invoices/static",
        "app": StaticFiles(directory="lnbits/extensions/invoices/static"),
        "name": "invoices_static",
    }
]

invoices_ext: APIRouter = APIRouter(prefix="/invoices", tags=["invoices"])


def invoices_renderer():
    return template_renderer(["lnbits/extensions/invoices/templates"])


from .tasks import wait_for_paid_invoices


def invoices_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))


from .views import *  # noqa
from .views_api import *  # noqa
