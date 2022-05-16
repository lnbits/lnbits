from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_discordbot")

discordbot_static_files = [
    {
        "path": "/discordbot/static",
        "app": StaticFiles(directory="lnbits/extensions/discordbot/static"),
        "name": "discordbot_static",
    }
]

discordbot_ext: APIRouter = APIRouter(prefix="/discordbot", tags=["discordbot"])


def discordbot_renderer():
    return template_renderer(["lnbits/extensions/discordbot/templates"])


from .views import *  # noqa
from .views_api import *  # noqa
