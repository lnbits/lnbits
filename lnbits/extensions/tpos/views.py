from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import (
    LNBITS_CUSTOM_LOGO,
    LNBITS_SITE_TITLE,
)

from . import tpos_ext, tpos_renderer
from .crud import get_tpos

templates = Jinja2Templates(directory="templates")


@tpos_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return tpos_renderer().TemplateResponse(
        "tpos/index.html", {"request": request, "user": user.dict()}
    )


@tpos_ext.get("/{tpos_id}")
async def tpos(request: Request, tpos_id):
    tpos = await get_tpos(tpos_id)
    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    return tpos_renderer().TemplateResponse(
        "tpos/tpos.html", {"request": request, "tpos": tpos}
    )

@tpos_ext.get("/manifest/{tpos_id}.webmanifest")
async def manifest(tpos_id: str):
    tpos = await get_tpos(tpos_id)
    if not tpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    return {
        "short_name": LNBITS_SITE_TITLE,
        "name": tpos.name + ' - ' + LNBITS_SITE_TITLE,
        "icons": [
            {
                "src": LNBITS_CUSTOM_LOGO if LNBITS_CUSTOM_LOGO else "https://cdn.jsdelivr.net/gh/lnbits/lnbits@0.3.0/docs/logos/lnbits.png",
                "type": "image/png",
                "sizes": "900x900",
            }
        ],
        "start_url": "/tpos/" + tpos_id,
        "background_color": "#1F2234",
        "description": "Bitcoin Lightning tPOS",
        "display": "standalone",
        "scope": "/tpos/" + tpos_id,
        "theme_color": "#1F2234",
        "shortcuts": [
            {
                "name": tpos.name + ' - ' + LNBITS_SITE_TITLE,
                "short_name": tpos.name,
                "description": tpos.name + ' - ' + LNBITS_SITE_TITLE,
                "url": "/tpos/" + tpos_id,
            }
        ],
    }