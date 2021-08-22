from fastapi import APIRouter

from lnbits.db import Database

db = Database("ext_offlineshop")

offlineshop_ext: APIRouter = APIRouter(
    prefix="/Extension",
    tags=["Offlineshop"]
)


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa
