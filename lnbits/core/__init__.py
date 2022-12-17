from fastapi.routing import APIRouter

from lnbits.db import Database

db = Database("database")

core_app: APIRouter = APIRouter()

from .views.admin_api import *  # noqa
from .views.api import *  # noqa
from .views.generic import *  # noqa
from .views.public_api import *  # noqa
