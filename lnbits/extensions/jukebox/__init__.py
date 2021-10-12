import asyncio
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_jukebox")

jukebox_static_files = [
    {
        "path": "/jukebox/static",
        "app": StaticFiles(directory="lnbits/extensions/jukebox/static"),
        "name": "jukebox_static",
    }
]

jukebox_ext: APIRouter = APIRouter(prefix="/jukebox", tags=["jukebox"])


def jukebox_renderer():
    return template_renderer(
        [
            "lnbits/extensions/jukebox/templates",
        ]
    )


from .views_api import *  # noqa
from .views import *  # noqa
from .tasks import wait_for_paid_invoices


def jukebox_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
