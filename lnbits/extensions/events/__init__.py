from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_events")


events_ext: APIRouter = APIRouter(
    prefix="/events",
    tags=["Events"]
)

def events_renderer():
    return template_renderer(["lnbits/extensions/events/templates"])
    
from .views import *  # noqa
from .views_api import *  # noqa
