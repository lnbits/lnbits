from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_hivemind")

hivemind_ext: APIRouter = APIRouter(
    prefix="/hivemind",
    tags=["hivemind"]
)

def hivemind_renderer():
    return template_renderer(["lnbits/extensions/hivemind/templates"])


from .views import *  # noqa
