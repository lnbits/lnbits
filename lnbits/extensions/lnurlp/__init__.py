import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_lnurlp")

lnurlp_static_files = [
    {
        "path": "/lnurlp/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/lnurlp/static")]),
        "name": "lnurlp_static",
    }
]

lnurlp_ext: APIRouter = APIRouter(prefix="/lnurlp", tags=["lnurlp"])


def lnurlp_renderer():
    return template_renderer(["lnbits/extensions/lnurlp/templates"])


from .lnurl import *  # noqa
from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def lnurlp_start():
    loop = asyncio.get_event_loop()
    loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
