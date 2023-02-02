import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_livestream")

livestream_static_files = [
    {
        "path": "/livestream/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/livestream/static")]),
        "name": "livestream_static",
    }
]

livestream_ext: APIRouter = APIRouter(prefix="/livestream", tags=["livestream"])


def livestream_renderer():
    return template_renderer(["lnbits/extensions/livestream/templates"])


from .lnurl import *  # noqa: F401,F403
from .tasks import wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


def livestream_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
