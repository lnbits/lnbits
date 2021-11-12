from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_paywall")

paywall_ext: APIRouter = APIRouter(prefix="/paywall", tags=["Paywall"])


def paywall_renderer():
    return template_renderer(["lnbits/extensions/paywall/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
