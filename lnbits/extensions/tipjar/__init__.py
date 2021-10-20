from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_tipjar")

tipjar_ext: APIRouter = APIRouter(prefix="/tipjar", tags=["tipjar"])


def tipjar_renderer():
    return template_renderer(["lnbits/extensions/tipjar/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
