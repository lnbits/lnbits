import asyncio
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_ngrok")

ngrok_ext: APIRouter = APIRouter(prefix="/ngrok", tags=["ngrok"])


def ngrok_renderer():
    return template_renderer(["lnbits/extensions/ngrok/templates"])


from .views import *
