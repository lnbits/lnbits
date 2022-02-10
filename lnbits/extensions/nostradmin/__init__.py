from fastapi import APIRouter, Request

from lnbits.db import Database
from lnbits.helpers import template_renderer

from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from http import HTTPStatus

from lnbits.settings import LNBITS_ADMIN_EXTENSIONS

nostradmin_ext: APIRouter = APIRouter(prefix="/nostradmin", tags=["nostradmin"])

db = Database("ext_nostradmin")
if 'nostradmin' not in LNBITS_ADMIN_EXTENSIONS:
    @nostradmin_ext.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return template_renderer().TemplateResponse(
                "error.html", {"request": request, "err": "NostrAdmin must be added to LNBITS_ADMIN_EXTENSIONS in .env"}
            )
else:
    
    def nostr_renderer():
        return template_renderer(["lnbits/extensions/nostradmin/templates"])

    from .views import *  # noqa
    from .views_api import *  # noqa










