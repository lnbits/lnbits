import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_pushnotifications")

pushnotifications_static_files = [
    {
        "path": "/pushnotifications/static",
        "app": StaticFiles(directory="lnbits/extensions/pushnotifications/static"),
        "name": "pushnotifications_static",
    }
]

pushnotifications_ext: APIRouter = APIRouter(
    prefix="/pushnotifications", tags=["pushnotifications"]
)


def pushnotifications_renderer():
    return template_renderer(["lnbits/extensions/pushnotifications/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
from .tasks import wait_for_paid_invoices, create_vapid_key_pair


def pushnotifications_start():
    create_vapid_key_pair()
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
