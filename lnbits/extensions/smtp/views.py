from http import HTTPStatus

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import smtp_ext, smtp_renderer
from .crud import get_emailaddress

templates = Jinja2Templates(directory="templates")


@smtp_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return smtp_renderer().TemplateResponse(
        "smtp/index.html", {"request": request, "user": user.dict()}
    )


@smtp_ext.get("/{emailaddress_id}")
async def display(request: Request, emailaddress_id):
    emailaddress = await get_emailaddress(emailaddress_id)
    if not emailaddress:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Emailaddress does not exist."
        )

    return smtp_renderer().TemplateResponse(
        "smtp/display.html",
        {
            "request": request,
            "emailaddress_id": emailaddress.id,
            "email": emailaddress.email,
            "desc": emailaddress.description,
            "cost": emailaddress.cost,
        },
    )
