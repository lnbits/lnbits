import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_jukebox")

jukebox_static_files = [
    {
        "path": "/jukebox/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/jukebox/static")]),
        "name": "jukebox_static",
    }
]

jukebox_ext: APIRouter = APIRouter(prefix="/jukebox", tags=["jukebox"])


def jukebox_renderer():
    return template_renderer(["lnbits/extensions/jukebox/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def jukebox_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
