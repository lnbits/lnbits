import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_boltz")

boltz_ext: APIRouter = APIRouter(prefix="/boltz", tags=["boltz"])


def boltz_renderer():
    return template_renderer(["lnbits/extensions/boltz/templates"])


boltz_static_files = [
    {
        "path": "/boltz/static",
        "app": StaticFiles(directory="lnbits/extensions/boltz/static"),
        "name": "boltz_static",
    }
]

from .tasks import check_for_pending_swaps, wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


def boltz_start():
    loop = asyncio.get_event_loop()
    loop.create_task(check_for_pending_swaps())
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
