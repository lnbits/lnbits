from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_lnurlpayout")

lnurlpayout_ext: APIRouter = APIRouter(prefix="/lnurlpayout", tags=["lnurlpayout"])


def lnurlpayout_renderer():
    return template_renderer(["lnbits/extensions/lnurlpayout/templates"])


from .views_api import *  # noqa
from .views import *  # noqa
