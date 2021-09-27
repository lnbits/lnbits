from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_lnticket")

lnticket_ext: APIRouter = APIRouter(
    prefix="/lnticket",
    tags=["LNTicket"]
    # "lnticket", __name__, static_folder="static", template_folder="templates"
)

def lnticket_renderer():
    return template_renderer(
        [
            "lnbits/extensions/lnticket/templates",
        ]
    )


from .views_api import *  # noqa
from .views import *  # noqa

@lntickets_ext.on_event("startup")
def _do_it():
    register_listeners()
