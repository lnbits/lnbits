import asyncio
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_lndhub")

lndhub_ext: APIRouter = APIRouter(prefix="/lndhub", tags=["lndhub"])


def lndhub_renderer():
    return template_renderer(
        [
            "lnbits/extensions/lndhub/templates",
        ]
    )


from .views_api import *  # noqa
from .views import *  # noqa
from .utils import *  # noqa
from .decorators import *  # noqa
