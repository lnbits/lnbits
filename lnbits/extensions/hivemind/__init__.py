from quart import Blueprint
from lnbits.db import Database

db = Database("ext_hivemind")

hivemind_ext: Blueprint = Blueprint(
    "hivemind", __name__, static_folder="static", template_folder="templates"
)


from .views import *  # noqa
