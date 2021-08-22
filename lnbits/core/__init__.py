from fastapi.routing import APIRouter

from lnbits.db import Database

db = Database("database")

core_app: APIRouter = APIRouter()

from lnbits.tasks import record_async

from .tasks import register_listeners
from .views.api import *  # noqa
from .views.generic import *  # noqa
from .views.public_api import *  # noqa


@core_app.on_event("startup")
def do_startup():
     record_async(register_listeners)
