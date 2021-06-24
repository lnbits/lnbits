from . import db
from .models import Donation, Service

from ..satspay.crud import delete_charge

import httpx

from http import HTTPStatus
from quart import jsonify

from typing import Optional

from lnbits.helpers import urlsafe_short_hash
from lnbits.core.crud import get_wallet


async def get_charge_details(service_id):
    details = {
        "description": f"TwitchAlerts donation for service {str(service_id)}",
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
    cur_code: str,
    sats: int,
    amount: float,
    service: int,
    name: str = "Anonymous",
    message: str = "",
    posted: bool = False,
) -> Donation:
    await db.execute(
        """
        INSERT INTO Donations (
            id,
            name,
            message,
            cur_code,
            sats,
            amount,
            service,
            posted
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id,
            name,
            message,
            cur_code,
            sats,
            amount,
            service,
            posted
        ),
    )
    return await get_donation(id)


async def post_donation(donation_id: str) -> tuple:
    donation = await get_donation(donation_id)
    if not donation:
        return (
            jsonify({"message": "Donation not found!"}),
            HTTPStatus.BAD_REQUEST
        )
    if donation.posted:
        return (
            jsonify({"message": "Donation has already been posted!"}),
            HTTPStatus.BAD_REQUEST
        )
    service = await get_service(donation.service)
    if service.servicename == "Streamlabs":
        url = "https://streamlabs.com/api/v1.0/donations"
        data = {
                "name": donation.name,
                "message": donation.message,
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
            HTTPStatus.BAD_REQUEST
        )
    else:
        return (
            jsonify({"message": "Unsopported servicename"}),
            HTTPStatus.BAD_REQUEST
        )
    await db.execute(
        "UPDATE Donations SET posted = 1 WHERE id = ?",
        (donation_id,)
    )
    return (
        jsonify(response.json()),
        status
    )


async def create_service(
    twitchuser: str,
    client_id: str,
    client_secret: str,
    wallet: str,
    servicename: str,
    state: str = None,
    onchain: str = None,
) -> Service:
    result = await db.execute(
        """
        INSERT INTO Services (
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
    service_id = result._result_proxy.lastrowid
    service = await get_service(service_id)
    return service


async def get_service(service_id: int) -> Optional[Service]:
    row = await db.fetchone(
        "SELECT * FROM Services WHERE id = ?",
        (service_id,)
    )
    return Service.from_row(row) if row else None


async def authenticate_service(service_id, code, redirect_uri):
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
    token = response['access_token']
    success = await service_add_token(service_id, token)
    return f"/twitchalerts/?usr={user}", success


async def service_add_token(service_id, token):
    if (await get_service(service_id)).authenticated:
        return False
    await db.execute(
        "UPDATE Services SET authenticated = 1, token = ? where id = ?",
        (token, service_id,),
    )
    return True


async def delete_service(service_id: int) -> None:
    await db.execute(
        "DELETE FROM Services WHERE id = ?",
        (service_id,)
    )
    rows = await db.fetchall(
        "SELECT * FROM Donations WHERE service = ?",
        (service_id,)
    )
    for row in rows:
        await delete_donation(row["id"])


async def get_donation(donation_id: str) -> Optional[Donation]:
    row = await db.fetchone(
        "SELECT * FROM Donations WHERE id = ?",
        (donation_id,)
    )
    return Donation.from_row(row) if row else None


async def delete_donation(donation_id: str) -> None:
    await db.execute(
        "DELETE FROM Donations WHERE id = ?",
        (donation_id,)
    )
    await delete_charge(donation_id)
