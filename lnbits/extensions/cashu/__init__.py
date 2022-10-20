import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_cashu")

import sys

sys.path.append("/Users/moto/Documents/GitHub/motorina0/cashu")
# from lnbits.extensions.cashu.ledger_crud import LedgerCrud

cashu_static_files = [
    {
        "path": "/cashu/static",
        "app": StaticFiles(directory="lnbits/extensions/cashu/static"),
        "name": "cashu_static",
    }
]


# from cashu.mint.ledger import Ledger

# ledger = Ledger(
#     db=db,
#     crud=LedgerCrud(db, "x"),  # remove this instance
#     # seed=MINT_PRIVATE_KEY,
#     seed="asd",
#     derivation_path="0/0/0/1",
# )

cashu_ext: APIRouter = APIRouter(prefix="/cashu", tags=["cashu"])


def cashu_renderer():
    return template_renderer(["lnbits/extensions/cashu/templates"])


from .tasks import startup_cashu_mint, wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def cashu_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(startup_cashu_mint))
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
