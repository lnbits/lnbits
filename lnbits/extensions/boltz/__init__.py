import asyncio

from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_boltz")

boltz_ext: APIRouter = APIRouter(prefix="/boltz", tags=["boltz"])


def boltz_renderer():
    return template_renderer(["lnbits/extensions/boltz/templates"])


from .tasks import check_for_pending_swaps, wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def boltz_start():
    loop = asyncio.get_event_loop()
    loop.create_task(check_for_pending_swaps())
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
