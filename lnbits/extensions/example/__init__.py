import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_example")

example_ext: APIRouter = APIRouter(prefix="/example", tags=["example"])

example_static_files = [
    {
        "path": "/example/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/example/static")]),
        "name": "example_static",
    }
]


def example_renderer():
    return template_renderer(["lnbits/extensions/example/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


def tpos_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
