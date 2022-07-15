from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_boltcards")

boltcards_ext: APIRouter = APIRouter(prefix="/boltcards", tags=["boltcards"])


def boltcards_renderer():
    return template_renderer(["lnbits/extensions/boltcards/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
