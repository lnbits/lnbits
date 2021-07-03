from quart import Blueprint

ngrok_ext: Blueprint = Blueprint("ngrok", __name__, template_folder="templates")

from .views import *  # noqa
