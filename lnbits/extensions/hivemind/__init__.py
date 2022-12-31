from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_hivemind")

hivemind_ext: APIRouter = APIRouter(prefix="/hivemind", tags=["hivemind"])


def hivemind_renderer():
    return template_renderer(["lnbits/extensions/hivemind/templates"])


hivemind_static_files = [
    {
        "path": "/hivemind/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/hivemind/static")]),
        "name": "hivemind_static",
    }
]

from .views import *  # noqa
