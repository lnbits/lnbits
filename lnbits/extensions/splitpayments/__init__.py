import asyncio
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_splitpayments")

splitpayments_static_files = [
    {
        "path": "/splitpayments/static",
        "app": StaticFiles(directory="lnbits/extensions/splitpayments/static"),
        "name": "splitpayments_static",
    }
]
splitpayments_ext: APIRouter = APIRouter(
    prefix="/splitpayments", tags=["splitpayments"]
)


def splitpayments_renderer():
    return template_renderer(["lnbits/extensions/splitpayments/templates"])


# from lnbits.tasks import record_async
# splitpayments_ext.record(record_async(register_listeners))


from .views_api import *  # noqa
from .views import *  # noqa
from .tasks import wait_for_paid_invoices


def splitpayments_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
