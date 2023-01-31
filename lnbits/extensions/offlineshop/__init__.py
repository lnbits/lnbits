from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_offlineshop")

offlineshop_static_files = [
    {
        "path": "/offlineshop/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/offlineshop/static")]),
        "name": "offlineshop_static",
    }
]

offlineshop_ext: APIRouter = APIRouter(prefix="/offlineshop", tags=["Offlineshop"])


def offlineshop_renderer():
    return template_renderer(["lnbits/extensions/offlineshop/templates"])


from .lnurl import *  # noqa: F401,F403
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403
