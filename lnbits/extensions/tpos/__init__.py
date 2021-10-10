import asyncio

from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_tpos")

tpos_ext: APIRouter = APIRouter(
    prefix="/tpos",
    tags=["TPoS"]
    # "tpos", __name__, static_folder="static", template_folder="templates"
)

def tpos_renderer():
    return template_renderer(
        [
            "lnbits/extensions/tpos/templates",
        ]
    )


from .views_api import *  # noqa
from .views import *  # noqa
