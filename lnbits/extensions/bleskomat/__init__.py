from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_bleskomat")

bleskomat_ext: APIRouter = APIRouter(
    prefix="/bleskomat",
    tags=["Bleskomat"]
)

def bleskomat_renderer():
    return template_renderer(["lnbits/extensions/events/templates"])

from .lnurl_api import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
