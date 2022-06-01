from http import HTTPStatus

# from mmap import MAP_DENYWRITE

from fastapi.param_functions import Depends
from fastapi.params import Query
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from lnbits.core.crud import get_wallet_payment
from lnbits.core.models import Payment, User
from lnbits.decorators import check_user_exists

from . import livestream_ext, livestream_renderer
from .crud import get_livestream_by_track, get_track


@livestream_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return livestream_renderer().TemplateResponse(
        "livestream/index.html", {"request": request, "user": user.dict()}
    )


@livestream_ext.get("/track/{track_id}", name="livestream.track_redirect_download")
async def track_redirect_download(track_id, p: str = Query(...)):
    payment_hash = p
    track = await get_track(track_id)
    ls = await get_livestream_by_track(track_id)
    payment: Payment = await get_wallet_payment(ls.wallet, payment_hash)

    if not payment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Couldn't find the payment {payment_hash} or track {track.id}.",
        )

    if payment.pending:
        raise HTTPException(
            status_code=HTTPStatus.PAYMENT_REQUIRED,
            detail=f"Payment {payment_hash} wasn't received yet. Please try again in a minute.",
        )
    return RedirectResponse(url=track.download_url)
