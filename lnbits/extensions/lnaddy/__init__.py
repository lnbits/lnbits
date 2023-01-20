import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_lnaddy")
maindb = Database("database")

lnaddy_ext: APIRouter = APIRouter(prefix="/lnaddy", tags=["lnaddy"])

lnaddy_static_files = [
    {
        "path": "/lnaddy/static",
        "app": StaticFiles(directory="lnbits/extensions/lnaddy/static"),
        "name": "lnaddy_static",
    }
]


def lnurlp_renderer():
    return template_renderer(["lnbits/extensions/lnaddy/templates"])


from .lnurl import *  # noqa
from .tasks import wait_for_paid_invoices  # noqa
from .views import *  # noqa
from .views_api import *  # noqa


def lnaddy_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
