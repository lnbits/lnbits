from http import HTTPStatus

from fastapi import Depends, Query
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type

# todo: use the API, not direct import
from lnbits.extensions.satspay.models import CreateCharge  # type: ignore
from lnbits.utils.exchange_rates import btc_price

# todo: use the API, not direct import
from ..satspay.crud import create_charge, get_charge  # type: ignore
from . import streamalerts_ext
from .crud import (
    authenticate_service,
    create_donation,
    create_service,
    delete_donation,
    delete_service,
    get_charge_details,
    get_donation,
    get_donations,
    get_service,
    get_service_redirect_uri,
    get_services,
    post_donation,
    update_donation,
    update_service,
)
from .models import CreateDonation, CreateService, ValidateDonation


@streamalerts_ext.post("/api/v1/services")
async def api_create_service(
    data: CreateService, wallet: WalletTypeInfo = Depends(get_key_type)
):
    """Create a service, which holds data about how/where to post donations"""
    try:
        service = await create_service(data=data)
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return service.dict()


@streamalerts_ext.get("/api/v1/getaccess/{service_id}")
async def api_get_access(service_id, request: Request):
    """Redirect to Streamlabs' Approve/Decline page for API access for Service
    with service_id
    """
    service = await get_service(service_id)
    if service:
        redirect_uri = await get_service_redirect_uri(request, service_id)
        params = {
            "response_type": "code",
            "client_id": service.client_id,
            "redirect_uri": redirect_uri,
            "scope": "donations.create",
            "state": service.state,
        }
        endpoint_url = "https://streamlabs.com/api/v1.0/authorize/?"
        querystring = "&".join([f"{key}={value}" for key, value in params.items()])
        redirect_url = endpoint_url + querystring
        return RedirectResponse(redirect_url)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Service does not exist!"
        )


@streamalerts_ext.get("/api/v1/authenticate/{service_id}")
async def api_authenticate_service(
    service_id, request: Request, code: str = Query(...), state: str = Query(...)
):
    """Endpoint visited via redirect during third party API authentication

    If successful, an API access token will be added to the service, and
    the user will be redirected to index.html.
    """

    service = await get_service(service_id)
    assert service

    if service.state != state:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="State doesn't match!"
        )

    redirect_uri = request.url.scheme + "://" + request.headers["Host"]
    redirect_uri += f"/streamalerts/api/v1/authenticate/{service_id}"
    url, success = await authenticate_service(service_id, code, redirect_uri)
    if success:
        return RedirectResponse(url)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Service already authenticated!"
        )


@streamalerts_ext.post("/api/v1/donations")
async def api_create_donation(data: CreateDonation, request: Request):
    """Take data from donation form and return satspay charge"""
    # Currency is hardcoded while frotnend is limited
    cur_code = "USD"
    sats = data.sats
    message = data.message
    # Fiat amount is calculated here while frontend is limited
    price = await btc_price(cur_code)
    amount = sats * (10 ** (-8)) * price
    webhook_base = request.url.scheme + "://" + request.headers["Host"]
    service_id = data.service
    service = await get_service(service_id)
    assert service
    charge_details = await get_charge_details(service.id)
    name = data.name if data.name else "Anonymous"

    description = f"{sats} sats donation from {name} to {service.twitchuser}"
    create_charge_data = CreateCharge(
        amount=sats,
        completelink=f"https://twitch.tv/{service.twitchuser}",
        completelinktext="Back to Stream!",
        webhook=webhook_base + "/streamalerts/api/v1/postdonation",
        description=description,
        **charge_details,
    )
    charge = await create_charge(user=charge_details["user"], data=create_charge_data)
    await create_donation(
        id=charge.id,
        wallet=service.wallet,
        message=message,
        name=name,
        cur_code=cur_code,
        sats=data.sats,
        amount=amount,
        service=data.service,
    )
    return {"redirect_url": f"/satspay/{charge.id}"}


@streamalerts_ext.post("/api/v1/postdonation")
async def api_post_donation(request: Request, data: ValidateDonation):
    """Post a paid donation to Stremalabs/StreamElements.
    This endpoint acts as a webhook for the SatsPayServer extension."""

    donation_id = data.id
    charge = await get_charge(donation_id)
    if charge and charge.paid:
        return await post_donation(donation_id)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Not a paid charge!"
        )


@streamalerts_ext.get("/api/v1/services")
async def api_get_services(g: WalletTypeInfo = Depends(get_key_type)):
    """Return list of all services assigned to wallet with given invoice key"""
    user = await get_user(g.wallet.user)
    wallet_ids = user.wallet_ids if user else []
    services = []
    for wallet_id in wallet_ids:
        new_services = await get_services(wallet_id)
        services += new_services if new_services else []
    return [service.dict() for service in services] if services else []


@streamalerts_ext.get("/api/v1/donations")
async def api_get_donations(g: WalletTypeInfo = Depends(get_key_type)):
    """Return list of all donations assigned to wallet with given invoice
    key
    """
    user = await get_user(g.wallet.user)
    wallet_ids = user.wallet_ids if user else []
    donations = []
    for wallet_id in wallet_ids:
        new_donations = await get_donations(wallet_id)
        donations += new_donations if new_donations else []
    return [donation.dict() for donation in donations] if donations else []


@streamalerts_ext.put("/api/v1/donations/{donation_id}")
async def api_update_donation(
    data: CreateDonation, donation_id=None, g: WalletTypeInfo = Depends(get_key_type)
):
    """Update a donation with the data given in the request"""
    if donation_id:
        donation = await get_donation(donation_id)

        if not donation:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Donation does not exist."
            )

        if donation.wallet != g.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your donation."
            )

        donation = await update_donation(donation_id, **data.dict())
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="No donation ID specified"
        )

    return donation.dict()


@streamalerts_ext.put("/api/v1/services/{service_id}")
async def api_update_service(
    data: CreateService, service_id=None, g: WalletTypeInfo = Depends(get_key_type)
):
    """Update a service with the data given in the request"""
    if service_id:
        service = await get_service(service_id)

        if not service:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Service does not exist."
            )

        if service.wallet != g.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your service."
            )

        service = await update_service(service_id, **data.dict())
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="No service ID specified"
        )
    return service.dict()


@streamalerts_ext.delete("/api/v1/donations/{donation_id}")
async def api_delete_donation(donation_id, g: WalletTypeInfo = Depends(get_key_type)):
    """Delete the donation with the given donation_id"""
    donation = await get_donation(donation_id)
    if not donation:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No donation with this ID!"
        )
    if donation.wallet != g.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this donation!",
        )
    await delete_donation(donation_id)
    return "", HTTPStatus.NO_CONTENT


@streamalerts_ext.delete("/api/v1/services/{service_id}")
async def api_delete_service(service_id, g: WalletTypeInfo = Depends(get_key_type)):
    """Delete the service with the given service_id"""
    service = await get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No service with this ID!"
        )
    if service.wallet != g.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this service!",
        )
    await delete_service(service_id)
    return "", HTTPStatus.NO_CONTENT
