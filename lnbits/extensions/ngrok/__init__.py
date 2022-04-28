from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_ngrok")

ngrok_ext: APIRouter = APIRouter(prefix="/ngrok", tags=["ngrok"])


def ngrok_renderer():
    return template_renderer(["lnbits/extensions/ngrok/templates"])


from .views import *
