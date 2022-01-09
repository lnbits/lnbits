from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import sendmail_ext, sendmail_renderer
from .crud import get_emailaddress

templates = Jinja2Templates(directory="templates")


@sendmail_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return sendmail_renderer().TemplateResponse(
        "sendmail/index.html", {"request": request, "user": user.dict()}
    )


@sendmail_ext.get("/{emailaddress_id}")
async def display(request: Request, emailaddress_id):
    emailaddress = await get_emailaddress(emailaddress_id)
    if not emailaddress:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Emailaddress does not exist."
        )

    return sendmail_renderer().TemplateResponse(
        "sendmail/display.html",
        {
            "request": request,
            "emailaddress_id": emailaddress.id,
            "email": emailaddress.email,
            "desc": emailaddress.description,
            "cost": emailaddress.cost,
        },
    )
