from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database('ext_jitsi')

jitsi_static_files = [
        {
            'path': '/jitsi/static',
            'app' : StaticFiles(directory = 'lnbits/extensions/jitsi/static'),
            'name': 'jitsi_static',
            }
        ]

jitsi_ext: APIRouter = APIRouter(
    prefix = '/jitsi', 
    tags = ['jitsi'],
)

def jitsi_renderer():
    return template_renderer(['lnbits/extensions/jitsi/templates'])


from .views_api import *  # noqa
from .views import *  # noqa
