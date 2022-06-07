import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_scrub")

scrub_static_files = [
    {
        "path": "/scrub/static",
        "app": StaticFiles(directory="lnbits/extensions/scrub/static"),
        "name": "scrub_static",
    }
]

scrub_ext: APIRouter = APIRouter(prefix="/scrub", tags=["scrub"])


def scrub_renderer():
    return template_renderer(["lnbits/extensions/scrub/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def scrub_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
