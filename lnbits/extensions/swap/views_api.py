from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import Request
from fastapi.params import Depends, Query
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import check_invoice_status, create_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.extensions.lnaddress.models import CreateAddress, CreateDomain

from . import swap_ext
from .crud import get_swapouts
from .etleneum import create_queue_pay


# SWAP OUT
@swap_ext.get("/api/v1/out")
async def api_swap_outs(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [swap.dict() for swap in await get_swapouts(wallet_ids)]

