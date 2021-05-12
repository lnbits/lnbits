from quart import Blueprint
from lnbits.db import Database

db = Database("ext_winlose")
wal_db = Database("database")

winlose_ext: Blueprint = Blueprint(
    "winlose", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
