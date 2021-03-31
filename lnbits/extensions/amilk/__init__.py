from quart import Blueprint
from lnbits.db import Database

db = Database("ext_amilk")

amilk_ext: Blueprint = Blueprint(
    "amilk", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
