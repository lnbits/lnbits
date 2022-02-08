from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_nostradmin")

nostr_ext: APIRouter = APIRouter(prefix="/nostradmin", tags=["nostradmin"])


def nostr_renderer():
    return template_renderer(["lnbits/extensions/nostradmin/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
