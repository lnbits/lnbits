from flask import Blueprint


core_app: Blueprint = Blueprint("core", __name__, template_folder="templates", static_folder="static")


from .views.api import *  # noqa
from .views.generic import *  # noqa
from .views.lnurl import *  # noqa
