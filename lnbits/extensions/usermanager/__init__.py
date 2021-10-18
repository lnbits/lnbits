from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_usermanager")

usermanager_ext: APIRouter = APIRouter(
    prefix="/usermanager",
    tags=["usermanager"]
)


def usermanager_renderer():
    return template_renderer(["lnbits/extensions/usermanager/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
