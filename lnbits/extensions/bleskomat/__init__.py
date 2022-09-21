from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_bleskomat")

bleskomat_static_files = [
    {
        "path": "/bleskomat/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/bleskomat/static")]),
        "name": "bleskomat_static",
    }
]

bleskomat_ext: APIRouter = APIRouter(prefix="/bleskomat", tags=["Bleskomat"])


def bleskomat_renderer():
    return template_renderer(["lnbits/extensions/bleskomat/templates"])


from .lnurl_api import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
