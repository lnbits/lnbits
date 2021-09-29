<<<<<<< HEAD
=======
from fastapi.param_functions import Depends
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User
>>>>>>> f827d2ce181d97368161d46ab8de2e9f061b9872
from lnbits.core.crud import get_wallet
from lnbits.decorators import check_user_exists
from http import HTTPStatus

from . import lnticket_ext, lnticket_renderer
from .crud import get_form
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@lnticket_ext.get("/", response_class=HTMLResponse)
# not needed as we automatically get the user with the given ID
# If no user with this ID is found, an error is raised
# @validate_uuids(["usr"], required=True) 
# @check_user_exists()
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnticket_renderer().TemplateResponse("lnticket/index.html", {"request": request,"user": user.dict()})


@lnticket_ext.get("/{form_id}")
async def display(request: Request, form_id):
    form = await get_form(form_id)
    if not form:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="LNTicket does not exist."
        )
        # abort(HTTPStatus.NOT_FOUND, "LNTicket does not exist.")

    wallet = await get_wallet(form.wallet)

    return lnticket_renderer().TemplateResponse(
        "lnticket/display.html",
        {"request": request,
        "form_id":form.id,
        "form_name":form.name,
        "form_desc":form.description,
        "form_amount":form.amount,
        "form_flatrate":form.flatrate,
        "form_wallet":wallet.inkey}
    )
