from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_admin")

admin_ext: APIRouter = APIRouter(prefix="/admin", tags=["admin"])


def admin_renderer():
    return template_renderer(["lnbits/extensions/admin/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
