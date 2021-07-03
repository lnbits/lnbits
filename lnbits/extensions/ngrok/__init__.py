from quart import Blueprint
from lnbits.db import Database

db = Database("ext_ngrok")

ngrok_ext: Blueprint = Blueprint("ngrok", __name__, template_folder="templates")

from .views import *  # noqa
