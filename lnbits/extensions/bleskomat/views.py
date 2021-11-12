from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import bleskomat_ext, bleskomat_renderer
from .exchange_rates import exchange_rate_providers_serializable, fiat_currencies
from .helpers import get_callback_url

templates = Jinja2Templates(directory="templates")


@bleskomat_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    bleskomat_vars = {
        "callback_url": get_callback_url(request=request),
        "exchange_rate_providers": exchange_rate_providers_serializable,
        "fiat_currencies": fiat_currencies,
    }
    return bleskomat_renderer().TemplateResponse(
        "bleskomat/index.html",
        {"request": request, "user": user.dict(), "bleskomat_vars": bleskomat_vars},
    )
