import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_podcast")

podcast_static_files = [
    {
        "path": "/podcast/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/podcast/static")]),
        "name": "podcast_static",
    }
]

podcast_ext: APIRouter = APIRouter(prefix="/podcast", tags=["podcast"])

def podcast_renderer():
    return template_renderer(["lnbits/extensions/podcast/templates"])

from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def podcast_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
