from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_boltcards")

boltcards_static_files = [
    {
        "path": "/boltcards/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/boltcards/static")]),
        "name": "boltcards_static",
    }
]

boltcards_ext: APIRouter = APIRouter(prefix="/boltcards", tags=["boltcards"])


def boltcards_renderer():
    return template_renderer(["lnbits/extensions/boltcards/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
