from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_example")

example_ext: APIRouter = APIRouter(prefix="/example", tags=["example"])


def example_renderer():
    return template_renderer(["lnbits/extensions/example/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
