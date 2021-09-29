from fastapi import APIRouter

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
from .tasks import register_listeners

@lnticket_ext.on_event("startup")
def _do_it():
    # FIXME: isn't called yet
    register_listeners()
