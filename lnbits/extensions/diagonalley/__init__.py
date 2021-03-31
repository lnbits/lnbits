from quart import Blueprint


diagonalley_ext: Blueprint = Blueprint(
    "diagonalley", __name__, static_folder="static", template_folder="templates"
)


from .views_api import *  # noqa
from .views import *  # noqa
