import asyncio
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_lnurlpos")

lnurlpos_ext: APIRouter = APIRouter(prefix="/lnurlpos", tags=["lnurlpos"])


def lnurlpos_renderer():
    return template_renderer(["lnbits/extensions/lnurlpos/templates"])


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa
