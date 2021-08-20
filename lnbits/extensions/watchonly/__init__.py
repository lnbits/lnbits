from quart import Blueprint
from lnbits.db import Database

db = Database("ext_watchonly")


watchonly_ext: Blueprint = Blueprint(
    "watchonly", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
