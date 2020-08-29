from flask import Blueprint


lnurlp_ext: Blueprint = Blueprint("lnurlp", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
