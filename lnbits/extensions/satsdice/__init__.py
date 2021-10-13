import asyncio
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("satsdice_ext")

satsdice_ext: APIRouter = APIRouter(prefix="/satsdice", tags=["satsdice"])


def satsdice_renderer():
    return template_renderer(
        [
            "lnbits/extensions/satsdice/templates",
        ]
    )


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa
from .tasks import wait_for_paid_invoices


def satsdice_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
