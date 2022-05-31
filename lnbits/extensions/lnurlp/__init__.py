from quart import Blueprint
from lnbits.db import Database

db = Database("ext_lnurlp")

lnurlp_ext: Blueprint = Blueprint(
    "lnurlp", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa
from .tasks import register_listeners

from lnbits.tasks import record_async

lnurlp_ext.record(record_async(register_listeners))
