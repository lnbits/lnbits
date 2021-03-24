from quart import Blueprint
from lnbits.db import Database

db = Database("ext_bleskomat")

bleskomat_ext: Blueprint = Blueprint(
    "bleskomat", __name__, static_folder="static", template_folder="templates"
)

from .lnurl_api import *  # noqa
from .views_api import *  # noqa
from .views import *  # noqa
