from fastapi import APIRouter

from lnbits.db import Database

db = Database("ext_withdraw")


withdraw_ext: APIRouter = APIRouter(
    prefix="/withdraw",
    static_folder="static"
    # "withdraw", __name__, static_folder="static", template_folder="templates"
)

def withdraw_renderer():
    return template_renderer(
        [
            "lnbits/extensions/withdraw/templates",
        ]
    )


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa

@withdraw_ext.on_event("startup")
def _do_it():
    register_listeners()
