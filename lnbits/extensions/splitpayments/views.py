from http import HTTPStatus
from lnbits.decorators import check_user_exists, WalletTypeInfo, get_key_type
from . import splitpayments_ext, splitpayments_renderer
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User, Payment

templates = Jinja2Templates(directory="templates")


@splitpayments_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return splitpayments_renderer().TemplateResponse(
        "splitpayments/index.html", {"request": request, "user": user.dict()}
    )
