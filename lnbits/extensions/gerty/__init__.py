import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_gerty")

gerty_static_files = [
    {
        "path": "/gerty/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/gerty/static")]),
        "name": "gerty_static",
    }
]


gerty_ext: APIRouter = APIRouter(prefix="/gerty", tags=["Gerty"])


def gerty_renderer():
    return template_renderer(["lnbits/extensions/gerty/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
