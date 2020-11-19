from quart import Blueprint

from lnbits.db import Database

db = Database("ext_livestream")

livestream_ext: Blueprint = Blueprint("livestream", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa
from .tasks import register_listeners

from lnbits.tasks import record_async

livestream_ext.record(record_async(register_listeners))
