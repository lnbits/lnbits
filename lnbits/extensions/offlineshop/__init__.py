from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_offlineshop")

offlineshop_static_files = [
    {
        "path": "/offlineshop/static",
        "app": StaticFiles(directory="lnbits/extensions/offlineshop/static"),
        "name": "offlineshop_static",
    }
]

offlineshop_ext: APIRouter = APIRouter(
    prefix="/offlineshop",
    tags=["Offlineshop"],
    # routes=[
    #     Mount(
    #         "/static",
    #         app=StaticFiles(directory="lnbits/extensions/offlineshop/static"),
    #         name="offlineshop_static",
    #     )
    # ],
)


def offlineshop_renderer():
    return template_renderer(
        [
            "lnbits/extensions/offlineshop/templates",
        ]
    )


from .lnurl import *  # noqa
from .views import *  # noqa
from .views_api import *  # noqa
