from typing import Optional
from pydantic.main import BaseModel
from quart import g, redirect, request, jsonify
from http import HTTPStatus

from lnbits.decorators import api_validate_post_request, api_check_wallet_key
from lnbits.core.crud import get_user
from lnbits.utils.exchange_rates import btc_price

from . import streamalerts_ext
from .crud import (
    get_charge_details,
    get_service_redirect_uri,
    create_donation,
    post_donation,
    get_donation,
    get_donations,
    delete_donation,
    create_service,
    get_service,
    get_services,
    authenticate_service,
    update_donation,
    update_service,
    delete_service,
)
from ..satspay.crud import create_charge, get_charge

class CreateServicesData(BaseModel):
    twitchuser:  str
    client_id:  str
    client_secret:  str
    wallet:  str
    servicename:  str
    onchain:  Optional[str]

@streamalerts_ext.post("/api/v1/services")
@api_check_wallet_key("invoice")
async def api_create_service(data: CreateServicesData):
    """Create a service, which holds data about how/where to post donations"""
    try:
        service = await create_service(**data)
    except Exception as e:
        return {"message": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR

    return service._asdict(), HTTPStatus.CREATED


@streamalerts_ext.get("/api/v1/getaccess/{service_id}")
async def api_get_access(service_id):
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
        return redirect(redirect_url)
    else:
        return ({"message": "Service does not exist!"}, HTTPStatus.BAD_REQUEST)


@streamalerts_ext.get("/api/v1/authenticate/{service_id}")
async def api_authenticate_service(Code: str, State: str, service_id):
    """Endpoint visited via redirect during third party API authentication

    If successful, an API access token will be added to the service, and
    the user will be redirected to index.html.
    """
    code = Code
    state = State
    service = await get_service(service_id)
    if service.state != state:
        return ({"message": "State doesn't match!"}, HTTPStatus.BAD_Request)
    redirect_uri = request.scheme + "://" + request.headers["Host"]
    redirect_uri += f"/streamalerts/api/v1/authenticate/{service_id}"
    url, success = await authenticate_service(service_id, code, redirect_uri)
    if success:
        return redirect(url)
    else:
        return ({"message": "Service already authenticated!"},
            HTTPStatus.BAD_REQUEST,
        )

class CreateDonationsData(BaseModel):
    name:  str
    sats:  int
    service:  int
    message:  str

@streamalerts_ext.post("/api/v1/donations")
async def api_create_donation(data:CreateDonationsData):
    """Take data from donation form and return satspay charge"""
    # Currency is hardcoded while frotnend is limited
    cur_code = "USD"
    sats = data.sats
    message = data.message
    # Fiat amount is calculated here while frontend is limited
    price = await btc_price(cur_code)
    amount = sats * (10 ** (-8)) * price
    webhook_base = request.scheme + "://" + request.headers["Host"]
    service_id = data.service
    service = await get_service(service_id)
    charge_details = await get_charge_details(service.id)
    name = data.name
    if not name:
        name = "Anonymous"
    description = f"{sats} sats donation from {name} to {service.twitchuser}"
    charge = await create_charge(
        amount=sats,
        completelink=f"https://twitch.tv/{service.twitchuser}",
        completelinktext="Back to Stream!",
        webhook=webhook_base + "/streamalerts/api/v1/postdonation",
        description=description,
        **charge_details,
    )
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
    return ({"redirect_url": f"/satspay/{charge.id}"}), HTTPStatus.OK


@streamalerts_ext.post("/api/v1/postdonation")

async def api_post_donation(id: str):
    """Post a paid donation to Stremalabs/StreamElements.

    This endpoint acts as a webhook for the SatsPayServer extension."""
    data = await request.get_json(force=True)
    donation_id = id
    charge = await get_charge(donation_id)
    if charge and charge.paid:
        return await post_donation(donation_id)
    else:
        return ({"message": "Not a paid charge!"}, HTTPStatus.BAD_REQUEST)


@streamalerts_ext.get("/api/v1/services")
@api_check_wallet_key("invoice")
async def api_get_services():
    """Return list of all services assigned to wallet with given invoice key"""
    wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    services = []
    for wallet_id in wallet_ids:
        new_services = await get_services(wallet_id)
        services += new_services if new_services else []
    return (
        [service._asdict() for service in services] if services else [],
        HTTPStatus.OK,
    )


@streamalerts_ext.get("/api/v1/donations")
@api_check_wallet_key("invoice")
async def api_get_donations():
    """Return list of all donations assigned to wallet with given invoice
    key
    """
    wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    donations = []
    for wallet_id in wallet_ids:
        new_donations = await get_donations(wallet_id)
        donations += new_donations if new_donations else []
    return (
        [donation._asdict() for donation in donations] if donations else [],
        HTTPStatus.OK,
    )


@streamalerts_ext.put("/api/v1/donations/{donation_id}")
@api_check_wallet_key("invoice")
async def api_update_donation(donation_id=None):
    """Update a donation with the data given in the request"""
    if donation_id:
        donation = await get_donation(donation_id)

        if not donation:
            return (
                {"message": "Donation does not exist."},
                HTTPStatus.NOT_FOUND,
            )

        if donation.wallet != g.wallet.id:
            return ({"message": "Not your donation."}, HTTPStatus.FORBIDDEN)

        donation = await update_donation(donation_id, **g.data)
    else:
        return (
            {"message": "No donation ID specified"},
            HTTPStatus.BAD_REQUEST,
        )
    return donation._asdict(), HTTPStatus.CREATED


@streamalerts_ext.put("/api/v1/services/{service_id}")
@api_check_wallet_key("invoice")
async def api_update_service(service_id=None):
    """Update a service with the data given in the request"""
    if service_id:
        service = await get_service(service_id)

        if not service:
            return ({"message": "Service does not exist."},
                HTTPStatus.NOT_FOUND,
            )

        if service.wallet != g.wallet.id:
            return ({"message": "Not your service."}), HTTPStatus.FORBIDDEN

        service = await update_service(service_id, **g.data)
    else:
        return ({"message": "No service ID specified"}), HTTPStatus.BAD_REQUEST
    return service._asdict(), HTTPStatus.CREATED


@streamalerts_ext.delete("/api/v1/donations/{donation_id}")
@api_check_wallet_key("invoice")
async def api_delete_donation(donation_id):
    """Delete the donation with the given donation_id"""
    donation = await get_donation(donation_id)
    if not donation:
        return ({"message": "No donation with this ID!"}, HTTPStatus.NOT_FOUND)
    if donation.wallet != g.wallet.id:
        return ({"message": "Not authorized to delete this donation!"},
            HTTPStatus.FORBIDDEN,
        )
    await delete_donation(donation_id)

    return "", HTTPStatus.NO_CONTENT


@streamalerts_ext.delete("/api/v1/services/{service_id}")
@api_check_wallet_key("invoice")
async def api_delete_service(service_id):
    """Delete the service with the given service_id"""
    service = await get_service(service_id)
    if not service:
        return ({"message": "No service with this ID!"}, HTTPStatus.NOT_FOUND)
    if service.wallet != g.wallet.id:
        return (
            {"message": "Not authorized to delete this service!"},
            HTTPStatus.FORBIDDEN,
        )
    await delete_service(service_id)

    return "", HTTPStatus.NO_CONTENT
