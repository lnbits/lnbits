from quart import Blueprint
from lnbits.db import Database

db = Database("database")

core_app: Blueprint = Blueprint(
    "core",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/core/static",
)


from .views.api import *  # noqa
from .views.generic import *  # noqa
from .views.public_api import *  # noqa
from .tasks import register_listeners

from lnbits.tasks import record_async

core_app.record(record_async(register_listeners))
