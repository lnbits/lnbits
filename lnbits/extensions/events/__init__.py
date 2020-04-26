from flask import Blueprint


events_ext: Blueprint = Blueprint("events", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
