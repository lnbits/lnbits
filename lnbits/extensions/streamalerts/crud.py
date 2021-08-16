from . import db
from .models import Donation, Service

from ..satspay.crud import delete_charge  # type: ignore

import httpx

from http import HTTPStatus
from quart import jsonify

from typing import Optional

from lnbits.db import SQLITE
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.crud import get_wallet


async def get_service_redirect_uri(request, service_id):
    """Return the service's redirect URI, to be given to the third party API"""
    uri_base = request.scheme + "://"
    uri_base += request.headers["Host"] + "/streamalerts/api/v1"
    redirect_uri = uri_base + f"/authenticate/{service_id}"
    return redirect_uri


async def get_charge_details(service_id):
    """Return the default details for a satspay charge

    These might be different depending for services implemented in the future.
    """
    details = {
        "time": 1440,
    }
    service = await get_service(service_id)
    wallet_id = service.wallet
    wallet = await get_wallet(wallet_id)
    user = wallet.user
    details["user"] = user
    details["lnbitswallet"] = wallet_id
    details["onchainwallet"] = service.onchain
    return details


async def create_donation(
    id: str,
    wallet: str,
    cur_code: str,
    sats: int,
    amount: float,
    service: int,
    name: str = "Anonymous",
    message: str = "",
    posted: bool = False,
) -> Donation:
    """Create a new Donation"""
    await db.execute(
        """
        INSERT INTO streamalerts.Donations (
            id,
            wallet,
            name,
            message,
            cur_code,
            sats,
            amount,
            service,
            posted
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (id, wallet, name, message, cur_code, sats, amount, service, posted),
    )

    donation = await get_donation(id)
    assert donation, "Newly created donation couldn't be retrieved"
    return donation


async def post_donation(donation_id: str) -> tuple:
    """Post donations to their respective third party APIs

    If the donation has already been posted, it will not be posted again.
    """
    donation = await get_donation(donation_id)
    if not donation:
        return (jsonify({"message": "Donation not found!"}), HTTPStatus.BAD_REQUEST)
    if donation.posted:
        return (
            jsonify({"message": "Donation has already been posted!"}),
            HTTPStatus.BAD_REQUEST,
        )
    service = await get_service(donation.service)
    assert service, "Couldn't fetch service to donate to"

    if service.servicename == "Streamlabs":
        url = "https://streamlabs.com/api/v1.0/donations"
        data = {
            "name": donation.name[:25],
            "message": donation.message[:255],
            "identifier": "LNbits",
            "amount": donation.amount,
            "currency": donation.cur_code.upper(),
            "access_token": service.token,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
        print(response.json())
        status = [s for s in list(HTTPStatus) if s == response.status_code][0]
    elif service.servicename == "StreamElements":
        return (
            jsonify({"message": "StreamElements not yet supported!"}),
            HTTPStatus.BAD_REQUEST,
        )
    else:
        return (jsonify({"message": "Unsopported servicename"}), HTTPStatus.BAD_REQUEST)
    await db.execute(
        "UPDATE streamalerts.Donations SET posted = 1 WHERE id = ?", (donation_id,)
    )
    return (jsonify(response.json()), status)


async def create_service(
    twitchuser: str,
    client_id: str,
    client_secret: str,
    wallet: str,
    servicename: str,
    state: str = None,
    onchain: str = None,
) -> Service:
    """Create a new Service"""

    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await (method)(
        f"""
        INSERT INTO streamalerts.Services (
            twitchuser,
            client_id,
            client_secret,
            wallet,
            servicename,
            authenticated,
            state,
            onchain
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        {returning}
        """,
        (
            twitchuser,
            client_id,
            client_secret,
            wallet,
            servicename,
            False,
            urlsafe_short_hash(),
            onchain,
        ),
    )
    if db.type == SQLITE:
        service_id = result._result_proxy.lastrowid
    else:
        service_id = result[0]

    service = await get_service(service_id)
    assert service
    return service


async def get_service(service_id: int, by_state: str = None) -> Optional[Service]:
    """Return a service either by ID or, available, by state

    Each Service's donation page is reached through its "state" hash
    instead of the ID, preventing accidental payments to the wrong
    streamer via typos like 2 -> 3.
    """
    if by_state:
        row = await db.fetchone(
            "SELECT * FROM streamalerts.Services WHERE state = ?", (by_state,)
        )
    else:
        row = await db.fetchone(
            "SELECT * FROM streamalerts.Services WHERE id = ?", (service_id,)
        )
    return Service.from_row(row) if row else None


async def get_services(wallet_id: str) -> Optional[list]:
    """Return all services belonging assigned to the wallet_id"""
    rows = await db.fetchall(
        "SELECT * FROM streamalerts.Services WHERE wallet = ?", (wallet_id,)
    )
    return [Service.from_row(row) for row in rows] if rows else None


async def authenticate_service(service_id, code, redirect_uri):
    """Use authentication code from third party API to retreive access token"""
    # The API token is passed in the querystring as 'code'
    service = await get_service(service_id)
    wallet = await get_wallet(service.wallet)
    user = wallet.user
    url = "https://streamlabs.com/api/v1.0/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": service.client_id,
        "client_secret": service.client_secret,
        "redirect_uri": redirect_uri,
    }
    print(data)
    async with httpx.AsyncClient() as client:
        response = (await client.post(url, data=data)).json()
    print(response)
    token = response["access_token"]
    success = await service_add_token(service_id, token)
    return f"/streamalerts/?usr={user}", success


async def service_add_token(service_id, token):
    """Add access token to its corresponding Service

    This also sets authenticated = 1 to make sure the token
    is not overwritten.
    Tokens for Streamlabs never need to be refreshed.
    """
    if (await get_service(service_id)).authenticated:
        return False
    await db.execute(
        "UPDATE streamalerts.Services SET authenticated = 1, token = ? where id = ?",
        (
            token,
            service_id,
        ),
    )
    return True


async def delete_service(service_id: int) -> None:
    """Delete a Service and all corresponding Donations"""
    await db.execute("DELETE FROM streamalerts.Services WHERE id = ?", (service_id,))
    rows = await db.fetchall(
        "SELECT * FROM streamalerts.Donations WHERE service = ?", (service_id,)
    )
    for row in rows:
        await delete_donation(row["id"])


async def get_donation(donation_id: str) -> Optional[Donation]:
    """Return a Donation"""
    row = await db.fetchone(
        "SELECT * FROM streamalerts.Donations WHERE id = ?", (donation_id,)
    )
    return Donation.from_row(row) if row else None


async def get_donations(wallet_id: str) -> Optional[list]:
    """Return all streamalerts.Donations assigned to wallet_id"""
    rows = await db.fetchall(
        "SELECT * FROM streamalerts.Donations WHERE wallet = ?", (wallet_id,)
    )
    return [Donation.from_row(row) for row in rows] if rows else None


async def delete_donation(donation_id: str) -> None:
    """Delete a Donation and its corresponding statspay charge"""
    await db.execute("DELETE FROM streamalerts.Donations WHERE id = ?", (donation_id,))
    await delete_charge(donation_id)


async def update_donation(donation_id: str, **kwargs) -> Donation:
    """Update a Donation"""
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE streamalerts.Donations SET {q} WHERE id = ?",
        (*kwargs.values(), donation_id),
    )
    row = await db.fetchone(
        "SELECT * FROM streamalerts.Donations WHERE id = ?", (donation_id,)
    )
    assert row, "Newly updated donation couldn't be retrieved"
    return Donation(**row)


async def update_service(service_id: str, **kwargs) -> Service:
    """Update a service"""
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE streamalerts.Services SET {q} WHERE id = ?",
        (*kwargs.values(), service_id),
    )
    row = await db.fetchone(
        "SELECT * FROM streamalerts.Services WHERE id = ?", (service_id,)
    )
    assert row, "Newly updated service couldn't be retrieved"
    return Service(**row)
