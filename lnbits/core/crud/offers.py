from time import time
from typing import Optional, Tuple

from lnbits.core.db import db
from lnbits.core.models import OfferState
from lnbits.db import Connection, DateTrunc, Filters, Page

from ..models import (
    CreateOffer,
    Offer,
    OfferFilters,
    OffersStatusCount,
)


async def get_offer(offer_id: str, conn: Optional[Connection] = None) -> Offer:
    return await (conn or db).fetchone(
        "SELECT * FROM apioffers WHERE offer_id = :offer_id",
        {"offer_id": offer_id},
        Offer,
    )


async def get_standalone_offer(
    offer_id: str,
    conn: Optional[Connection] = None,
    wallet_id: Optional[str] = None,
) -> Optional[Offer]:
    clause: str = "offer_id = :offer_id"
    values = {
        "wallet_id": wallet_id,
        "offer_id": offer_id,
    }

    if wallet_id:
        clause = f"({clause}) AND wallet_id = :wallet_id"

    row = await (conn or db).fetchone(
        f"""
        SELECT * FROM apioffers
        WHERE {clause}
        """,
        values,
        Offer,
    )
    return row


async def get_offers_paginated(
    *,
    wallet_id: Optional[str] = None,
    active: Optional[bool] = None,
    single_use: Optional[bool] = None,
    since: Optional[int] = None,
    filters: Optional[Filters[OfferFilters]] = None,
    conn: Optional[Connection] = None,
) -> Page[Offer]:
    """
    Filters offers to be returned by:
      - active | single_use.
    """

    values: dict = {
        "wallet_id": wallet_id,
        "created_at": since,
    }
    clause: list[str] = []

    if since is not None:
        clause.append(f"created_at > {db.timestamp_placeholder('time')}")

    if wallet_id:
        clause.append("wallet_id = :wallet_id")

    if active is not None:
        clause.append("active = :active")

    if single_use is not None:
        clause.append("single_use = :single_use")

    return await (conn or db).fetch_page(
        "SELECT * FROM apioffers",
        clause,
        values,
        filters=filters,
        model=Offer,
    )


async def get_offers(
    *,
    wallet_id: Optional[str] = None,
    active: Optional[bool] = None,
    single_use: Optional[bool] = None,
    since: Optional[int] = None,
    filters: Optional[Filters[OfferFilters]] = None,
    conn: Optional[Connection] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[Offer]:
    """
    Filters offers to be returned by active | single_use.
    """

    filters = filters or Filters()

    filters.sortby = filters.sortby or "created_at"
    filters.direction = filters.direction or "desc"
    filters.limit = limit or filters.limit
    filters.offset = offset or filters.offset

    page = await get_offers_paginated(
        wallet_id=wallet_id,
        active=active,
        single_use=single_use,
        since=since,
        filters=filters,
        conn=conn,
    )

    return page.data


async def get_offers_status_count() -> OffersStatusCount:
    empty_page: Filters = Filters(limit=0)
    active_offers = await get_offers_paginated(active=True, filters=empty_page)
    single_use_offers = await get_offers_paginated(single_use=True, filters=empty_page)

    return OffersStatusCount(
        active=active_offers.total,
        single_use=single_use_offers.total,
    )


async def delete_expired_offers(
    conn: Optional[Connection] = None,
) -> None:
    # We delete all offers whose expiry date is in the past
    await (conn or db).execute(
        f"""
        DELETE FROM apioffers
        WHERE expiry < {db.timestamp_placeholder("now")}
        """,
        {"now": int(time())},
    )


async def create_offer(
    offer_id: str,
    wallet_id: str,
    bolt12: str,
    data: CreateOffer,
    active: OfferState,
    single_use: OfferState,
    conn: Optional[Connection] = None,
) -> Offer:
    # we don't allow the creation of the same offer twice
    # note: this can be removed if the db uniqueness constraints are set appropriately
    previous_offer = await get_standalone_offer(offer_id, conn=conn)
    assert previous_offer is None, "Offer already exists"
    extra = data.extra or {}

    offer = Offer(
        offer_id=offer_id,
        wallet_id=wallet_id,
        amount=data.amount_msat,
        active=active,
        single_use=single_use,
        bolt12=bolt12,
        memo=data.memo,
        expiry=data.expiry,
        webhook=data.webhook,
        tag=extra.get("tag", None),
        extra=extra,
    )
    print(offer)

    await (conn or db).insert("apioffers", offer)

    return offer


async def update_offer(
    offer: Offer,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).update(
        "apioffers", offer, "WHERE offer_id = :offer_id"
    )


async def delete_wallet_offer(
    offer_id: str, wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "DELETE FROM apioffers WHERE offer_id = :offer_id AND wallet = :wallet",
        {"offer_id": offer_id, "wallet": wallet_id},
    )


async def enable_offer(offer_id: str) -> None:
    await db.execute(
        f"""
        UPDATE apioffers SET active = :active, updated_at = {db.timestamp_placeholder("now")}
        WHERE offer_id = :offer_id
        """,
        {"now": time(), "offer_id": offer_id, "active": OfferState.TRUE},
    )


async def disable_offer(offer_id: str) -> None:
    await db.execute(
        f"""
        UPDATE apioffers SET active = :active, updated_at = {db.timestamp_placeholder("now")}
        WHERE offer_id = :offer_id
        """,
        {"now": time(), "offer_id": offer_id, "active": OfferState.FALSE},
    )


async def mark_webhook_offer_sent(offer_id: str, status: int) -> None:
    await db.execute(
        """
        UPDATE apioffers SET webhook_status = :status
        WHERE offer_id = :offer_id
        """,
        {"status": status, "offer_id": offer_id},
    )
