from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_satsdice")

satsdice_ext: APIRouter = APIRouter(prefix="/satsdice", tags=["satsdice"])


def satsdice_renderer():
    return template_renderer(["lnbits/extensions/satsdice/templates"])


from .lnurl import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
