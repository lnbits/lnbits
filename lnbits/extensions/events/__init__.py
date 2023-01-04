import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_events")


events_ext: APIRouter = APIRouter(prefix="/events", tags=["Events"])

events_static_files = [
    {
        "path": "/events/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/events/static")]),
        "name": "events_static",
    }
]


def events_renderer():
    return template_renderer(["lnbits/extensions/events/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def events_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
