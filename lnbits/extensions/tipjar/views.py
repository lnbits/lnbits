from .crud import get_tipjar

from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists

from functools import wraps
import hashlib
from lnbits.core.services import check_invoice_status
from lnbits.core.crud import update_payment_status, get_standalone_payment
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from fastapi.params import Depends
from fastapi.param_functions import Query
import random

from datetime import datetime
from http import HTTPStatus
from . import tipjar_ext, tipjar_renderer
from lnbits.core.models import User, Payment

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
    print(tipjar_id)
    if not tipjar:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TipJar does not exist."
        )

    return tipjar_renderer().TemplateResponse(
        "tipjar/display.html",
        {"request": request, "donatee": tipjar.name, "tipjar": tipjar.id},
    )
