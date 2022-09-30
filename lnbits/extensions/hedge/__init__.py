import asyncio
from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_hedge")

hedge_ext: APIRouter = APIRouter(prefix="/hedge", tags=["hedge"])


def hedge_renderer():
    return template_renderer(["lnbits/extensions/hedge/templates"])


from .tasks import wait_for_paid_invoices, wait_for_sent_payments
from .views import *  # noqa
from .views_api import *  # noqa


def hedge_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
    loop.create_task(catch_everything_and_restart(wait_for_sent_payments))
