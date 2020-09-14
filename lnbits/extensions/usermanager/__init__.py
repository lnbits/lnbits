from quart import Blueprint


usermanager_ext: Blueprint = Blueprint("usermanager", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
