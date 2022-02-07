from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.lnurldevice import lnurldevice_ext
from lnbits.utils.exchange_rates import currencies

from . import lnurldevice_ext
from .crud import (
    create_lnurldevice,
    delete_lnurldevice,
    get_lnurldevice,
    get_lnurldevices,
    update_lnurldevice,
)
from .models import createLnurldevice


@nostr_ext.get("/api/v1/lnurlpos")
async def api_check_daemon(wallet: WalletTypeInfo = Depends(get_key_type)):
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    try:
        return [
            {**lnurldevice.dict()} for lnurldevice in await get_lnurldevices(wallet_ids)
        ]
    except:
        return ""

@nostr_ext.delete("/api/v1/lnurlpos/{lnurldevice_id}")
async def api_lnurldevice_delete(
    wallet: WalletTypeInfo = Depends(require_admin_key),
    lnurldevice_id: str = Query(None),
):
    lnurldevice = await get_lnurldevice(lnurldevice_id)

    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet link does not exist."
        )

    await delete_lnurldevice(lnurldevice_id)

    return "", HTTPStatus.NO_CONTENT