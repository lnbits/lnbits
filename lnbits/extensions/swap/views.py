from urllib.parse import urlparse

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import Payment, User
from lnbits.decorators import check_user_exists
from lnbits.extensions.swap.crud import get_recurrents
from lnbits.extensions.swap.tasks import on_invoice_paid

from . import swap_ext, swap_renderer

templates = Jinja2Templates(directory="templates")


@swap_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    root_url = urlparse(str(request.url)).netloc
    wallet_ids = [wallet.id for wallet in user.wallets]
    recurrents = await get_recurrents(wallet_ids)
    if recurrents:
        for rec in recurrents:
            mock_payment = Payment(
                checking_id="mock",
                pending=False,
                amount=1,
                fee=1,
                time=0000,
                bolt11="mock",
                preimage="mock",
                payment_hash="mock",
                wallet_id=rec.wallet,
            )
            await on_invoice_paid(mock_payment)

    return swap_renderer().TemplateResponse(
        "swap/index.html",
        {"request": request, "user": user.dict(), "root_url": root_url},
    )
