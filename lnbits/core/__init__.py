from quart import Blueprint


core_app: Blueprint = Blueprint(
    "core", __name__, template_folder="templates", static_folder="static", static_url_path="/core/static"
)


from .views.api import *  # noqa
from .views.generic import *  # noqa
from .tasks import grab_app_for_later

core_app.record(grab_app_for_later)
