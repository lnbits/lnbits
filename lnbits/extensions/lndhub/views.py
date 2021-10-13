from lnbits.decorators import check_user_exists
from . import lndhub_ext, lndhub_renderer
from fastapi import FastAPI, Request
from fastapi.params import Depends
from lnbits.core.models import User


@lndhub_ext.get("/")
async def lndhub_index(request: Request, user: User = Depends(check_user_exists)):
    return lndhub_renderer().TemplateResponse(
        "lndhub/index.html", {"request": request, "user": user.dict()}
    )
