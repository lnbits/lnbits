from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_streamalerts")

streamalerts_ext: APIRouter = APIRouter(prefix="/streamalerts", tags=["streamalerts"])

streamalerts_static_files = [
    {
        "path": "/streamalerts/static",
        "app": StaticFiles(directory="lnbits/extensions/streamalerts/static"),
        "name": "streamalerts_static",
    }
]


def streamalerts_renderer():
    return template_renderer(["lnbits/extensions/streamalerts/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
