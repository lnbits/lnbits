from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User
from lnbits.core.crud import get_wallet
from lnbits.decorators import check_user_exists
from http import HTTPStatus

from . import tpos_ext, tpos_renderer
from .crud import get_tpos
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


@tpos_ext.get("/", response_class=HTMLResponse)
# @validate_uuids(["usr"], required=True)
# @check_user_exists()
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
        # abort(HTTPStatus.NOT_FOUND, "TPoS does not exist.")

    return tpos_renderer().TemplateResponse(
        "tpos/tpos.html", {"request": request, "tpos": tpos}
    )
