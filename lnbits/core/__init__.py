from fastapi.routing import APIRouter

from lnbits.core.models import CoreAppExtra
from lnbits.db import Database

db = Database("database")

core_app: APIRouter = APIRouter(tags=["Core"])

core_app_extra: CoreAppExtra = CoreAppExtra()

from .views.admin_api import *
from .views.api import *
from .views.generic import *
from .views.public_api import *
