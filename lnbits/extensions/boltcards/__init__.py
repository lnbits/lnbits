import asyncio

from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_boltcards")

boltcards_static_files = [
    {
        "path": "/boltcards/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/boltcards/static")]),
        "name": "boltcards_static",
    }
]

boltcards_ext: APIRouter = APIRouter(prefix="/boltcards", tags=["boltcards"])


def boltcards_renderer():
    return template_renderer(["lnbits/extensions/boltcards/templates"])


from .lnurl import *  # noqa: F401,F403
from .tasks import *  # noqa: F401,F403


def boltcards_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))  # noqa: F405


from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403
