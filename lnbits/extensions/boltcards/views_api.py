# views_api.py is for you API endpoints that could be hit by another service

# add your dependencies here

# import httpx
# (use httpx just like requests, except instead of response.ok there's only the
#  response.is_error that is its inverse)

import secrets
from http import HTTPStatus

from fastapi.params import Depends, Query
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.withdraw import get_withdraw_link

from . import boltcards_ext
from .crud import (
    create_card,
    create_hit,
    delete_card,
    get_all_cards,
    get_card,
    get_card_by_otp,
    get_cards,
    get_hits,
    update_card,
    update_card_counter,
    update_card_otp,
)
from .models import CreateCardData
from .nxp424 import decryptSUN, getSunMAC


@boltcards_ext.get("/api/v1/cards")
async def api_cards(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [card.dict() for card in await get_cards(wallet_ids)]


@boltcards_ext.post("/api/v1/cards", status_code=HTTPStatus.CREATED)
@boltcards_ext.put("/api/v1/cards/{card_id}", status_code=HTTPStatus.OK)
async def api_card_create_or_update(
    #    req: Request,
    data: CreateCardData,
    card_id: str = None,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    if(len(bytes.fromhex(data.uid)) != 7):
        raise HTTPException(
                detail="Invalid bytes for card uid.", status_code=HTTPStatus.BAD_REQUEST
            )

    if(len(bytes.fromhex(data.k0)) != 16):
        raise HTTPException(
                detail="Invalid bytes for k0.", status_code=HTTPStatus.BAD_REQUEST
            )

    if(len(bytes.fromhex(data.k1)) != 16):
        raise HTTPException(
                detail="Invalid bytes for k1.", status_code=HTTPStatus.BAD_REQUEST
            )

    if(len(bytes.fromhex(data.k2)) != 16):
        raise HTTPException(
                detail="Invalid bytes for k2.", status_code=HTTPStatus.BAD_REQUEST
            )

    if card_id:
        card = await get_card(card_id)
        if not card:
            raise HTTPException(
                detail="Card does not exist.", status_code=HTTPStatus.NOT_FOUND
            )
        if card.wallet != wallet.wallet.id:
            raise HTTPException(
                detail="Not your card.", status_code=HTTPStatus.FORBIDDEN
            )
        card = await update_card(card_id, **data.dict())
    else:
        card = await create_card(wallet_id=wallet.wallet.id, data=data)
    return card.dict()


@boltcards_ext.delete("/api/v1/cards/{card_id}")
async def api_card_delete(card_id, wallet: WalletTypeInfo = Depends(require_admin_key)):
    card = await get_card(card_id)

    if not card:
        raise HTTPException(
            detail="Card does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if card.wallet != wallet.wallet.id:
        raise HTTPException(detail="Not your card.", status_code=HTTPStatus.FORBIDDEN)

    await delete_card(card_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


@boltcards_ext.get("/api/v1/hits")
async def api_hits(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    cards = await get_cards(wallet_ids)
    cards_ids = []
    for card in cards:
        cards_ids.append(card.id)

    return [hit.dict() for hit in await get_hits(cards_ids)]


# /boltcards/api/v1/scan?p=00000000000000000000000000000000&c=0000000000000000
@boltcards_ext.get("/api/v1/scan")
async def api_scane(p, c, request: Request):
    # some wallets send everything as lower case, no bueno
    p = p.upper()
    c = c.upper()
    card = None
    counter = b""

    # since this route is common to all cards I don't know whitch 'meta key' to use
    # so I try one by one until decrypted uid matches
    for cand in await get_all_cards():
        if cand.k1:
            try:
                card_uid, counter = decryptSUN(bytes.fromhex(p), bytes.fromhex(cand.k1))

                if card_uid.hex().upper() == cand.uid:
                    card = cand
                    break
            except:
                continue

    if card == None:
        return {"status": "ERROR", "reason": "Unknown card."}

    if c != getSunMAC(card_uid, counter, bytes.fromhex(card.k2)).hex().upper():
        return {"status": "ERROR", "reason": "CMAC does not check."}

    ctr_int = int.from_bytes(counter, "little")
    if ctr_int <= card.counter:
        return {"status": "ERROR", "reason": "This link is already used."}

    await update_card_counter(ctr_int, card.id)

    # gathering some info for hit record
    ip = request.client.host
    if "x-real-ip" in request.headers:
        ip = request.headers["x-real-ip"]
    elif "x-forwarded-for" in request.headers:
        ip = request.headers["x-forwarded-for"]

    agent = request.headers["user-agent"] if "user-agent" in request.headers else ""

    await create_hit(card.id, ip, agent, card.counter, ctr_int)

    link = await get_withdraw_link(card.withdraw, 0)
    return link.lnurl_response(request)


# /boltcards/api/v1/auth?a=00000000000000000000000000000000
@boltcards_ext.get("/api/v1/auth")
async def api_auth(a, request: Request):
    if a == "00000000000000000000000000000000":
        response = {"k0": "0" * 32, "k1": "1" * 32, "k2": "2" * 32}
        return response

    card = await get_card_by_otp(a)

    if not card:
        raise HTTPException(
            detail="Card does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    new_otp = secrets.token_hex(16)
    print(card.otp)
    print(new_otp)
    await update_card_otp(new_otp, card.id)

    response = {"k0": card.k0, "k1": card.k1, "k2": card.k2}

    return response
