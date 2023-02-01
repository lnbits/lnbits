import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_smtp")

smtp_static_files = [
    {
        "path": "/smtp/static",
        "app": StaticFiles(directory="lnbits/extensions/smtp/static"),
        "name": "smtp_static",
    }
]

smtp_ext: APIRouter = APIRouter(prefix="/smtp", tags=["smtp"])


def smtp_renderer():
    return template_renderer(["lnbits/extensions/smtp/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


def smtp_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
