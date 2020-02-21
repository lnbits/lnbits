from flask import Blueprint


example_ext = Blueprint("example", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
