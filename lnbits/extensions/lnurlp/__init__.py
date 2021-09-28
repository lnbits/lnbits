from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount

from lnbits.db import Database

db = Database("ext_lnurlp")

lnurlp_ext: APIRouter = APIRouter(
    prefix="/lnurlp",
    static_folder="static",
    # "lnurlp", __name__, static_folder="static", template_folder="templates"
)

def lnurlp_renderer():
    return template_renderer(
        [
            "lnbits/extensions/lnticket/templates",
        ]
    )


from .views_api import *  # noqa
from .views import *  # noqa

@lnurlp_ext.on_event("startup")
def _do_it():
    register_listeners()

# from .lnurl import *  # noqa
# from .tasks import register_listeners

# from lnbits.tasks import record_async

# lnurlp_ext.record(record_async(register_listeners))
