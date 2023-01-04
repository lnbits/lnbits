from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Depends
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import lnticket_ext, lnticket_renderer
from .crud import get_form

templates = Jinja2Templates(directory="templates")


@lnticket_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnticket_renderer().TemplateResponse(
        "lnticket/index.html", {"request": request, "user": user.dict()}
    )


@lnticket_ext.get("/{form_id}")
async def display(request: Request, form_id):
    form = await get_form(form_id)
    if not form:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNTicket does not exist."
        )

    wallet = await get_wallet(form.wallet)
    assert wallet

    return lnticket_renderer().TemplateResponse(
        "lnticket/display.html",
        {
            "request": request,
            "form_id": form.id,
            "form_name": form.name,
            "form_desc": form.description,
            "form_amount": form.amount,
            "form_flatrate": form.flatrate,
            "form_wallet": wallet.inkey,
        },
    )
