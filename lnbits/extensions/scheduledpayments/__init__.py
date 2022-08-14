import asyncio

from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_scheduledpayments")

scheduledpayments_ext: APIRouter = APIRouter(
    prefix="/scheduledpayments", tags=["scheduledpayments"]
)


def scheduledpayments_renderer():
    return template_renderer(["lnbits/extensions/scheduledpayments/templates"])


from .tasks import wait_for_scheduled_payments


def scheduledpayments_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_scheduled_payments))


from .views import *  # noqa
from .views_api import *  # noqa
