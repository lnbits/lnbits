from fastapi import Depends, Request

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import lndhub_ext, lndhub_renderer


@lndhub_ext.get("/")
async def lndhub_index(request: Request, user: User = Depends(check_user_exists)):
    return lndhub_renderer().TemplateResponse(
        "lndhub/index.html", {"request": request, "user": user.dict()}
    )
