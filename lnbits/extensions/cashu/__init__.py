import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_cashu")

import sys

cashu_static_files = [
    {
        "path": "/cashu/static",
        "app": StaticFiles(directory="lnbits/extensions/cashu/static"),
        "name": "cashu_static",
    }
]
from cashu.mint.ledger import Ledger

ledger = Ledger(
    db=db,
    # seed=MINT_PRIVATE_KEY,
    seed="asd",
    derivation_path="0/0/0/1",
)

cashu_ext: APIRouter = APIRouter(prefix="/cashu", tags=["cashu"])


def cashu_renderer():
    return template_renderer(["lnbits/extensions/cashu/templates"])


from .tasks import wait_for_paid_invoices, startup_cashu_mint
from .views import *  # noqa
from .views_api import *  # noqa


def cashu_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(startup_cashu_mint))
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
