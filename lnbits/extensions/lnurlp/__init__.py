from quart import Blueprint


lnurlp_ext: Blueprint = Blueprint("lnurlp", __name__, static_folder="static", template_folder="templates")


from .views_api import *  # noqa
from .views import *  # noqa
from .tasks import on_invoice_paid

from lnbits.core.tasks import register_invoice_listener

register_invoice_listener("lnurlp", on_invoice_paid)
