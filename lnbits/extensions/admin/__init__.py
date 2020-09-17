from flask import Blueprint


admin_ext: Blueprint = Blueprint("admin", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
