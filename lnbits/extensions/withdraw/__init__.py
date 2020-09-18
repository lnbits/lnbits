from quart import Blueprint


withdraw_ext: Blueprint = Blueprint("withdraw", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
