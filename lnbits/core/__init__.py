from flask import Blueprint


core_app = Blueprint("core", __name__, template_folder="templates", static_folder="static")


from .views_api import *  # noqa
from .views import *  # noqa
