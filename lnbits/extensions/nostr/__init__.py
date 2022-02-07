from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_nostr")

nostr_ext: APIRouter = APIRouter(prefix="/nostr", tags=["nostr"])


def nostr_renderer():
    return template_renderer(["lnbits/extensions/nostr/templates"])


from .lnurl import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
