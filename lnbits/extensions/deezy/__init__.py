from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_deezy")

deezy_ext: APIRouter = APIRouter(prefix="/deezy", tags=["deezy"])

deezy_static_files = [
    {
        "path": "/deezy/static",
        "app": StaticFiles(directory="lnbits/extensions/deezy/static"),
        "name": "deezy_static",
    }
]


def deezy_renderer():
    return template_renderer(["lnbits/extensions/deezy/templates"])


from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403
