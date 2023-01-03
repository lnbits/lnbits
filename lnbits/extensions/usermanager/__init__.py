from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_usermanager")

usermanager_ext: APIRouter = APIRouter(prefix="/usermanager", tags=["usermanager"])

usermanager_static_files = [
    {
        "path": "/usermanager/static",
        "app": StaticFiles(directory="lnbits/extensions/usermanager/static"),
        "name": "usermanager_static",
    }
]


def usermanager_renderer():
    return template_renderer(["lnbits/extensions/usermanager/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
