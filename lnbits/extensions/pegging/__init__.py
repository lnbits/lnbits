import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_pegging")

pegging_ext: APIRouter = APIRouter(prefix="/pegging", tags=["Pegging"])

pegging_static_files = [
    {
        "path": "/pegging/static",
        "app": StaticFiles(directory="lnbits/extensions/pegging/static"),
        "name": "pegging_static",
    }
]


def pegging_renderer():
    return template_renderer(["lnbits/extensions/pegging/templates"])


from .tasks import wait_for_paid_invoices, hedge_loop
from .views import *  # noqa
from .views_api import *  # noqa


def pegging_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
    loop.create_task(catch_everything_and_restart(hedge_loop))
