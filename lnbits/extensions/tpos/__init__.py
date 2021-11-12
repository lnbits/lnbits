from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_tpos")

tpos_ext: APIRouter = APIRouter(prefix="/tpos", tags=["TPoS"])


def tpos_renderer():
    return template_renderer(["lnbits/extensions/tpos/templates"])


from .views_api import *  # noqa
from .views import *  # noqa
