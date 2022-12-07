from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_deezy")

deezy_ext: APIRouter = APIRouter(prefix="/deezy", tags=["deezy"])


def deezy_renderer():
    return template_renderer(["lnbits/extensions/deezy/templates"])


from .views import *  # noqa
