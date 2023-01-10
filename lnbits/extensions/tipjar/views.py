from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.param_functions import Query
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import tipjar_ext, tipjar_renderer
from .crud import get_tipjar

templates = Jinja2Templates(directory="templates")


@tipjar_ext.get("/")
async def index(request: Request, user: User = Depends(check_user_exists)):
    return tipjar_renderer().TemplateResponse(
        "tipjar/index.html", {"request": request, "user": user.dict()}
    )


@tipjar_ext.get("/{tipjar_id}")
async def tip(request: Request, tipjar_id: int = Query(None)):
    """Return the donation form for the Tipjar corresponding to id"""
    tipjar = await get_tipjar(tipjar_id)
    if not tipjar:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TipJar does not exist."
        )

    return tipjar_renderer().TemplateResponse(
        "tipjar/display.html",
        {"request": request, "donatee": tipjar.name, "tipjar": tipjar.id},
    )
