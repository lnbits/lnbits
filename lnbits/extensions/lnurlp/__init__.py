import asyncio

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_lnurlp")

lnurlp_static_files = [
    {
        "path": "/lnurlp/static",
        "app": StaticFiles(directory="lnbits/extensions/lnurlp/static"),
        "name": "lnurlp_static",
    }
]

lnurlp_ext: APIRouter = APIRouter(
    prefix="/lnurlp",
    tags=["lnurlp"]
    # "lnurlp", __name__, static_folder="static", template_folder="templates"
)


def lnurlp_renderer():
    return template_renderer(["lnbits/extensions/lnurlp/templates"])


from .views_api import *  # noqa
from .views import *  # noqa
from .tasks import wait_for_paid_invoices
from .lnurl import *  # noqa


def lnurlp_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))


# from lnbits.tasks import record_async

# lnurlp_ext.record(record_async(register_listeners))
