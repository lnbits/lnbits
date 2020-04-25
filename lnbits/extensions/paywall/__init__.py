from flask import Blueprint


paywall_ext: Blueprint = Blueprint("paywall", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
