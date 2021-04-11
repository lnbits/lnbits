from quart import Blueprint
from lnbits.db import Database

db = Database("ext_usermanager")

usermanager_ext: Blueprint = Blueprint(
    "usermanager", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
