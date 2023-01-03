from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_lndhub")

lndhub_ext: APIRouter = APIRouter(prefix="/lndhub", tags=["lndhub"])

lndhub_static_files = [
    {
        "path": "/lndhub/static",
        "app": StaticFiles(directory="lnbits/extensions/lndhub/static"),
        "name": "lndhub_static",
    }
]


def lndhub_renderer():
    return template_renderer(["lnbits/extensions/lndhub/templates"])


from .decorators import *  # noqa
from .utils import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
