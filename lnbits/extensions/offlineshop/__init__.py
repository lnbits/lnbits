from quart import Blueprint

from lnbits.db import Database

db = Database("ext_offlineshop")

offlineshop_ext: Blueprint = Blueprint(
    "offlineshop", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
from .lnurl import *  # noqa
