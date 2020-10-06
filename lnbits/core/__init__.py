from quart import Blueprint


core_app: Blueprint = Blueprint(
    "core", __name__, template_folder="templates", static_folder="static", static_url_path="/core/static"
)


from .views.api import *  # noqa
from .views.generic import *  # noqa
from .tasks import on_invoice_paid

from lnbits.tasks import register_invoice_listener

register_invoice_listener("core", on_invoice_paid)
