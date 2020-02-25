from flask import Blueprint


tpos_ext = Blueprint("tpos", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
