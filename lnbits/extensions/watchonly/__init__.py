from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_watchonly")

watchonly_static_files = [
    {
        "path": "/watchonly/static",
        "app": StaticFiles(directory="lnbits/extensions/watchonly/static"),
        "name": "watchonly_static",
    }
]

watchonly_ext: APIRouter = APIRouter(prefix="/watchonly", tags=["watchonly"])


def watchonly_renderer():
    return template_renderer(["lnbits/extensions/watchonly/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
