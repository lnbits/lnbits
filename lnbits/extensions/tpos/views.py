from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

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
    print(request.base_url)

    return tpos_renderer().TemplateResponse(
        "tpos/tpos.html", {"request": request, "tpos": tpos}
    )
