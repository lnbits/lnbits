from http import HTTPStatus

from fastapi import Depends, HTTPException, Query

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import boltcards_ext
from .crud import (
    create_card,
    delete_card,
    enable_disable_card,
    get_card,
    get_card_by_uid,
    get_cards,
    get_hits,
    get_refunds,
    update_card,
)
from .models import CreateCardData


@boltcards_ext.get("/api/v1/cards")
async def api_cards(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [card.dict() for card in await get_cards(wallet_ids)]


@boltcards_ext.post("/api/v1/cards", status_code=HTTPStatus.CREATED)
@boltcards_ext.put("/api/v1/cards/{card_id}", status_code=HTTPStatus.OK)
async def api_card_create_or_update(
    data: CreateCardData,
    card_id: str = Query(None),
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    try:
        if len(bytes.fromhex(data.uid)) != 7:
            raise HTTPException(
                detail="Invalid bytes for card uid.", status_code=HTTPStatus.BAD_REQUEST
            )

        if len(bytes.fromhex(data.k0)) != 16:
            raise HTTPException(
                detail="Invalid bytes for k0.", status_code=HTTPStatus.BAD_REQUEST
            )

        if len(bytes.fromhex(data.k1)) != 16:
            raise HTTPException(
                detail="Invalid bytes for k1.", status_code=HTTPStatus.BAD_REQUEST
            )

        if len(bytes.fromhex(data.k2)) != 16:
            raise HTTPException(
                detail="Invalid bytes for k2.", status_code=HTTPStatus.BAD_REQUEST
            )
    except:
        raise HTTPException(
            detail="Invalid byte data provided.", status_code=HTTPStatus.BAD_REQUEST
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
        checkUid = await get_card_by_uid(data.uid)
        if checkUid and checkUid.id != card_id:
            raise HTTPException(
                detail="UID already registered. Delete registered card and try again.",
                status_code=HTTPStatus.BAD_REQUEST,
            )
        card = await update_card(card_id, **data.dict())
    else:
        checkUid = await get_card_by_uid(data.uid)
        if checkUid:
            raise HTTPException(
                detail="UID already registered. Delete registered card and try again.",
                status_code=HTTPStatus.BAD_REQUEST,
            )
        card = await create_card(wallet_id=wallet.wallet.id, data=data)
    assert card
    return card.dict()


@boltcards_ext.get("/api/v1/cards/enable/{card_id}/{enable}", status_code=HTTPStatus.OK)
async def enable_card(
    card_id,
    enable,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    card = await get_card(card_id)
    if not card:
        raise HTTPException(detail="No card found.", status_code=HTTPStatus.NOT_FOUND)
    if card.wallet != wallet.wallet.id:
        raise HTTPException(detail="Not your card.", status_code=HTTPStatus.FORBIDDEN)
    card = await enable_disable_card(enable=enable, id=card_id)
    assert card
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
    return "", HTTPStatus.NO_CONTENT


@boltcards_ext.get("/api/v1/hits")
async def api_hits(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    cards = await get_cards(wallet_ids)
    cards_ids = []
    for card in cards:
        cards_ids.append(card.id)

    return [hit.dict() for hit in await get_hits(cards_ids)]


@boltcards_ext.get("/api/v1/refunds")
async def api_refunds(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    cards = await get_cards(wallet_ids)
    cards_ids = []
    for card in cards:
        cards_ids.append(card.id)
    hits = await get_hits(cards_ids)
    hits_ids = []
    for hit in hits:
        hits_ids.append(hit.id)

    return [refund.dict() for refund in await get_refunds(hits_ids)]
