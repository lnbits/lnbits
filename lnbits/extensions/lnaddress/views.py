from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import lnaddress_ext, lnaddress_renderer
from .crud import get_domain, purge_addresses

templates = Jinja2Templates(directory="templates")


@lnaddress_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnaddress_renderer().TemplateResponse(
        "lnaddress/index.html", {"request": request, "user": user.dict()}
    )


@lnaddress_ext.get("/{domain_id}", response_class=HTMLResponse)
async def display(domain_id, request: Request):
    domain = await get_domain(domain_id)
    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
        )

    await purge_addresses(domain_id)

    wallet = await get_wallet(domain.wallet)
    assert wallet
    url = urlparse(str(request.url))

    return lnaddress_renderer().TemplateResponse(
        "lnaddress/display.html",
        {
            "request": request,
            "domain_id": domain.id,
            "domain_domain": domain.domain,
            "domain_cost": domain.cost,
            "domain_wallet_inkey": wallet.inkey,
            "root_url": f"{url.scheme}://{url.netloc}",
        },
    )
