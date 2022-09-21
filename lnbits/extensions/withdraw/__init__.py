from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_withdraw")

withdraw_static_files = [
    {
        "path": "/withdraw/static",
        "app": StaticFiles(packages=[("lnbits", "extensions/withdraw/static")]),
        "name": "withdraw_static",
    }
]


withdraw_ext: APIRouter = APIRouter(prefix="/withdraw", tags=["withdraw"])


def withdraw_renderer():
    return template_renderer(["lnbits/extensions/withdraw/templates"])


from .lnurl import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
