import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_nostrrelay")

nostrrelay_ext: APIRouter = APIRouter(prefix="/nostrrelay", tags=["NostrRelay"])

nostrrelay_static_files = [
    {
        "path": "/nostrrelay/static",
        "app": StaticFiles(directory="lnbits/extensions/nostrrelay/static"),
        "name": "nostrrelay_static",
    }
]


def nostrrelay_renderer():
    return template_renderer(["lnbits/extensions/nostrrelay/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
