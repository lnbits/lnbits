from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_satspay")


satspay_ext: APIRouter = APIRouter(prefix="/satspay", tags=["satspay"])


def satspay_renderer():
    return template_renderer(["lnbits/extensions/satspay/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
