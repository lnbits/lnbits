from http import HTTPStatus
import asyncio
from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.nostr import nostr_ext
from lnbits.utils.exchange_rates import currencies

from . import nostr_ext
from lnbits.settings import LNBITS_ADMIN_USERS
from .crud import (
    create_nostrkeys,
    get_nostrkeys,
    create_nostrnotes,
    get_nostrnotes,
    create_nostrrelays,
    get_nostrrelays,
    get_nostrrelaylist,
    update_nostrrelayallowlist,
    update_nostrrelaydenylist,
    create_nostrconnections,
    get_nostrconnections,
)
from .models import nostrKeys, nostrCreateRelays, nostrRelayAllowList, nostrRelayDenyList


# while True:
async def nostr_subscribe():
    return
    # for the relays:
    # async with websockets.connect("ws://localhost:8765") as websocket:
    # for the public keys:
    # await websocket.send("subscribe to events")
    # await websocket.recv()


websocket_queue = asyncio.Queue(1000)


async def internal_invoice_listener():
    while True:
        checking_id = await internal_invoice_queue.get()
        asyncio.create_task(invoice_callback_dispatcher(checking_id))


@nostr_ext.get("/api/v1/relays")
async def api_relays_retrieve(wallet: WalletTypeInfo = Depends(get_key_type)):

    relays = await get_nostrrelays()
    if not relays:
        await create_nostrrelays(nostrCreateRelays(relay="wss://relayer.fiatjaf.com"))
        await create_nostrrelays(
            nostrCreateRelays(relay="wss://nostr-pub.wellorder.net")
        )
        relays = await get_nostrrelays()
    try:
        return [{**relays.dict()} for relays in await relays]
    except:
        None

@nostr_ext.get("/api/v1/relaylist")
async def api_relaylist(wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet.user not in LNBITS_ADMIN_USERS:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )
    return await get_nostrrelaylist()

@nostr_ext.post("/api/v1/allowlist")
async def api_relaysallowed(data: nostrRelayAllowList, wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet.user not in LNBITS_ADMIN_USERS:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )
    return await update_nostrrelayallowlist(data)

@nostr_ext.post("/api/v1/denylist")
async def api_relaysdenyed(data: nostrRelayDenyList, wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet.user not in LNBITS_ADMIN_USERS:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )
    return await update_nostrrelaydenylist(data)