import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_copilot")

copilot_static_files = [
    {
        "path": "/copilot/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/copilot/static")]),
        "name": "copilot_static",
    }
]
copilot_ext: APIRouter = APIRouter(prefix="/copilot", tags=["copilot"])


def copilot_renderer():
    return template_renderer(["lnbits/extensions/copilot/templates"])


from .lnurl import *  # noqa
from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def copilot_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
