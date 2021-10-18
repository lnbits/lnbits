from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_lndhub")

lndhub_ext: APIRouter = APIRouter(prefix="/lndhub", tags=["lndhub"])


def lndhub_renderer():
    return template_renderer(["lnbits/extensions/lndhub/templates"])


from .decorators import *  # noqa
from .utils import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
