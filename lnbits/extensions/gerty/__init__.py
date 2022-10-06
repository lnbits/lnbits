import asyncio

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_gerty")

gerty_ext: APIRouter = APIRouter(prefix="/gerty", tags=["Gerty"])

def gerty_renderer():
    return template_renderer(["lnbits/extensions/gerty/templates"])

from .views import *  # noqa
from .views_api import *  # noqa
