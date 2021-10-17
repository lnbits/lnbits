from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_withdraw")

withdraw_static_files = [
    {
        "path": "/withdraw/static",
        "app": StaticFiles(directory="lnbits/extensions/withdraw/static"),
        "name": "withdraw_static",
    }
]


withdraw_ext: APIRouter = APIRouter(
    prefix="/withdraw",
    tags=["withdraw"],
    # "withdraw", __name__, static_folder="static", template_folder="templates"
)


def withdraw_renderer():
    return template_renderer(["lnbits/extensions/withdraw/templates"])


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa


# @withdraw_ext.on_event("startup")
# def _do_it():
#     register_listeners()
