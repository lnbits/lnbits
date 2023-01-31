from fastapi.routing import APIRouter

from lnbits.core.models import CoreAppExtra
from lnbits.db import Database

db = Database("database")

core_app: APIRouter = APIRouter()

core_app_extra: CoreAppExtra = CoreAppExtra()

from .views.admin_api import *  # noqa: F401,F403
from .views.api import *  # noqa: F401,F403
from .views.generic import *  # noqa: F401,F403
from .views.public_api import *  # noqa: F401,F403
