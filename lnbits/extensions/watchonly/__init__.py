import asyncio

from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_watchonly")


watchonly_ext: APIRouter = APIRouter(prefix="/watchonly", tags=["watchonly"])


def watchonly_renderer():
    return template_renderer(["lnbits/extensions/watchonly/templates"])


from .views_api import *  # noqa
from .views import *  # noqa
