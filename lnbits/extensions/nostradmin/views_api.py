from http import HTTPStatus
import asyncio
from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.utils.exchange_rates import currencies

from lnbits.settings import LNBITS_ADMIN_USERS
from . import nostradmin_ext
from .crud import (
    create_nostrkeys,
    get_nostrkeys,
    create_nostrnotes,
    get_nostrnotes,
    create_nostrrelays,
    get_nostrrelays,
    get_nostrrelaylist,
    update_nostrrelaysetlist,
    create_nostrconnections,
    get_nostrconnections,
)
from .models import nostrKeys, nostrCreateRelays, nostrRelaySetList
from .views import relay_check

@nostradmin_ext.get("/api/v1/relays")
async def api_relays_retrieve(wallet: WalletTypeInfo = Depends(get_key_type)):
    relays = await get_nostrrelays()
    if not relays:
        await create_nostrrelays(nostrCreateRelays(relay="wss://relayer.fiatjaf.com"))
        await create_nostrrelays(
            nostrCreateRelays(relay="wss://nostr-pub.wellorder.net")
        )
        relays = await get_nostrrelays()
    if not relays:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )
    else:
        for relay in relays:
            relay.status = await relay_check(relay.relay)
        return relays



@nostradmin_ext.get("/api/v1/relaylist")
async def api_relaylist(wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet.user not in LNBITS_ADMIN_USERS:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )
    return await get_nostrrelaylist()

@nostradmin_ext.post("/api/v1/setlist")
async def api_relayssetlist(data: nostrRelaySetList, wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet.user not in LNBITS_ADMIN_USERS:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )
    return await update_nostrrelaysetlist(data)