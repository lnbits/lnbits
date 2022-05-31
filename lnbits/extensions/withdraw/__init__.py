from quart import Blueprint
from lnbits.db import Database

db = Database("ext_withdraw")


withdraw_ext: Blueprint = Blueprint(
    "withdraw", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa
