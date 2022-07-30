import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_satspay")


satspay_ext: APIRouter = APIRouter(prefix="/satspay", tags=["satspay"])

satspay_static_files = [
    {
        "path": "/satspay/static",
        "app": StaticFiles(directory="lnbits/extensions/satspay/static"),
        "name": "satspay_static",
    }
]


def satspay_renderer():
    return template_renderer(["lnbits/extensions/satspay/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def satspay_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
