import asyncio
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_tipjar")

tipjar_ext: APIRouter = APIRouter(prefix="/tipjar", tags=["tipjar"])


def tipjar_renderer():
    return template_renderer(["lnbits/extensions/tipjar/templates"])


from .views_api import *  # noqa
from .views import *  # noqa
