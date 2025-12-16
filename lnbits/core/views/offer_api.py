from http import HTTPStatus

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from lnbits.core.models import (
    CreateOffer,
    Offer,
    OfferFilters,
)
from lnbits.db import Filters, Page
from lnbits.decorators import (
    WalletTypeInfo,
    check_admin,
    parse_filters,
    require_invoice_key,
)
from lnbits.exceptions import OfferError
from lnbits.helpers import (
    generate_filter_params_openapi,
)

from ..crud import (
    get_offers,
    get_offers_paginated,
    get_standalone_offer,
)
from ..services import (
    create_offer,
    disable_offer,
    enable_offer,
)

offer_router = APIRouter(prefix="/api/v1/offers", tags=["Offers"])


@offer_router.get(
    "",
    name="Offer List",
    summary="get list of offers",
    response_description="list of offers",
    response_model=list[Offer],
    openapi_extra=generate_filter_params_openapi(OfferFilters),
)
async def api_offers(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
    filters: Filters = Depends(parse_filters(OfferFilters)),
):
    return await get_offers(
        wallet_id=key_info.wallet.id,
        filters=filters,
    )


@offer_router.get(
    "/paginated",
    name="Offer List",
    summary="get paginated list of offers",
    response_description="list of offers",
    response_model=Page[Offer],
    openapi_extra=generate_filter_params_openapi(OfferFilters),
)
async def api_offers_paginated(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
    filters: Filters = Depends(parse_filters(OfferFilters)),
):
    page = await get_offers_paginated(
        wallet_id=key_info.wallet.id,
        filters=filters,
    )
    return page


@offer_router.get(
    "/all/paginated",
    name="Offer List",
    summary="get paginated list of offers",
    response_description="list of offers",
    response_model=Page[Offer],
    openapi_extra=generate_filter_params_openapi(OfferFilters),
    dependencies=[Depends(check_admin)],
)
async def api_all_offers_paginated(
    filters: Filters = Depends(parse_filters(OfferFilters)),
):
    return await get_offers_paginated(
        filters=filters,
    )


@offer_router.post(
    "",
    summary="Create an offer",
    description="""
        This endpoint can be used to create an offer.
        To generate a new offer for receiving funds into the authorized account,
        specify at least the memo field in the POST body.
    """,
    status_code=HTTPStatus.CREATED,
    responses={
        520: {"description": "Offer error."},
    },
)
async def api_offers_create(
    offer_data: CreateOffer,
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> Offer:

    offer = await create_offer(
        wallet_id=key_info.wallet.id,
        amount_sat=offer_data.amount_msat / 1000 if offer_data.amount_msat else None,
        memo=offer_data.memo,
        absolute_expiry=offer_data.expiry,
        extra=offer_data.extra,
        webhook=offer_data.webhook,
    )
    return offer


@offer_router.get("/{offer_id}")
async def api_offer(
    offer_id,
    key_info: WalletTypeInfo = Depends(require_invoice_key),
):

    offer = await get_standalone_offer(offer_id, wallet_id=key_info.wallet.id)
    if offer is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Offer does not exist."
        )
    return offer


@offer_router.post(
    "/{offer_id}/enable",
    summary="Enable an offer",
    description="""
        This endpoint can be used to enable an offer.
    """,
    status_code=HTTPStatus.OK,
    responses={
        520: {"description": "Offer error."},
    },
)
async def api_offers_enable(
    offer_id,
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> bool:

    try:
        return await enable_offer(wallet_id=key_info.wallet.id, offer_id=offer_id)

    except OfferError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Offer could not be enabled",
        ) from exc


@offer_router.post(
    "/{offer_id}/disable",
    summary="Disable an offer",
    description="""
        This endpoint can be used to disable an offer.
    """,
    status_code=HTTPStatus.OK,
    responses={
        520: {"description": "Offer error."},
    },
)
async def api_offers_disable(
    offer_id,
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> bool:

    try:
        return await disable_offer(wallet_id=key_info.wallet.id, offer_id=offer_id)

    except OfferError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Offer could not be disabled",
        ) from exc
