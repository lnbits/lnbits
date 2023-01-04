from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_satsdice")

satsdice_ext: APIRouter = APIRouter(prefix="/satsdice", tags=["satsdice"])

satsdice_static_files = [
    {
        "path": "/satsdice/static",
        "app": StaticFiles(directory="lnbits/extensions/satsdice/static"),
        "name": "satsdice_static",
    }
]


def satsdice_renderer():
    return template_renderer(["lnbits/extensions/satsdice/templates"])


from .lnurl import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
