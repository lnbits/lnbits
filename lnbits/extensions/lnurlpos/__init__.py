from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_lnurlpos")

lnurlpos_ext: APIRouter = APIRouter(prefix="/lnurlpos", tags=["lnurlpos"])


def lnurlpos_renderer():
    return template_renderer(["lnbits/extensions/lnurlpos/templates"])


from .lnurl import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
