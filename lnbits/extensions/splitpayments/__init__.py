import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_splitpayments")

splitpayments_static_files = [
    {
        "path": "/splitpayments/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/splitpayments/static")]),
        "name": "splitpayments_static",
    }
]
splitpayments_ext: APIRouter = APIRouter(
    prefix="/splitpayments", tags=["splitpayments"]
)


def splitpayments_renderer():
    return template_renderer(["lnbits/extensions/splitpayments/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def splitpayments_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
