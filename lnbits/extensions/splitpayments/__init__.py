from quart import Blueprint

from lnbits.db import Database

db = Database("ext_splitpayments")

splitpayments_ext: Blueprint = Blueprint(
    "splitpayments", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
from .tasks import register_listeners

from lnbits.tasks import record_async

splitpayments_ext.record(record_async(register_listeners))
