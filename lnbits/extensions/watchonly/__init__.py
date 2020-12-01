from quart import Blueprint


watchonly_ext: Blueprint = Blueprint("watchonly", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
