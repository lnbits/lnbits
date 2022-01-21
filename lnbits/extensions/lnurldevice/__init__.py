from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_lnurldevice")

lnurldevice_ext: APIRouter = APIRouter(prefix="/lnurldevice", tags=["lnurldevice"])


def lnurldevice_renderer():
    return template_renderer(["lnbits/extensions/lnurldevice/templates"])


from .lnurl import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
