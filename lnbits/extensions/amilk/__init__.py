from flask import Blueprint


amilk_ext: Blueprint = Blueprint("amilk", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
