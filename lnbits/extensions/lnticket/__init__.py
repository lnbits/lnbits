from quart import Blueprint


lnticket_ext: Blueprint = Blueprint("lnticket", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
