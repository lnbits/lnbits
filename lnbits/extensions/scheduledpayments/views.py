import json

from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from pytz import all_timezones
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import scheduledpayments_ext, scheduledpayments_renderer

templates = Jinja2Templates(directory="templates")


@scheduledpayments_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return scheduledpayments_renderer().TemplateResponse(
        "scheduledpayments/index.html",
        {
            "request": request,
            "user": user.dict(),
            "all_timezones": json.dumps(all_timezones),
        },
    )
