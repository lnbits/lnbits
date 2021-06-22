from quart import g, redirect, request, jsonify
from http import HTTPStatus

from lnbits.decorators import api_validate_post_request, api_check_wallet_key

from . import twitchalerts_ext
from .crud import (
    get_charge_details,
    create_donation,
    post_donation,
    create_service,
    get_service,
    authenticate_service
)
from ..satspay.crud import create_charge, get_charge


@twitchalerts_ext.route("/api/v1/createservice", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "twitchuser": {"type": "string", "required": True},
        "client_id": {"type": "string", "required": True},
        "client_secret": {"type": "string", "required": True},
        "wallet": {"type": "string", "required": True},
        "servicename": {"type": "string", "required": True},
        "onchain": {"type": "string"}
    }
)
async def api_create_service():
    """Create a service, which holds data about how/where to post donations"""
    service = await create_service(**g.data)
    redirect_url = request.scheme + "://" + request.headers["Host"]
    redirect_url += f"/twitchalerts/?created={str(service.id)}"
    return redirect(redirect_url)


@twitchalerts_ext.route("/api/v1/getaccess/<service_id>", methods=["GET"])
async def api_get_access(service_id):
    service = await get_service(service_id)
    if service:
        uri_base = request.scheme + "://"
        uri_base += request.headers["Host"] + "/twitchalerts/api/v1"
        redirect_uri = uri_base + f"/authenticate/{service_id}"
        params = {
            "response_type": "code",
            "client_id": service.client_id,
            "client_secret": service.client_secret,
            "redirect_uri": redirect_uri,
            "scope": "donations.create",
            "state": service.state
        }
        endpoint_url = "https://streamlabs.com/api/v1.0/authorize/?"
        querystring = "&".join(
            [f"{key}={value}" for key, value in params.items()]
        )
        redirect_url = endpoint_url + querystring
        return redirect(redirect_url)
    else:
        return (
            jsonify({"message": "Service does not exist!"}),
            HTTPStatus.BAD_REQUEST
        )


@twitchalerts_ext.route("/api/v1/authenticate/<service_id>", methods=["GET"])
async def api_authenticate_service(service_id):
    code = request.args.get('code')
    state = request.args.get('state')
    service = await get_service(service_id)
    if service.state != state:
        return (
            jsonify({"message": "State doesn't match!"}),
            HTTPStatus.BAD_Request
        )
    redirect_uri = f"/twitchalerts/api/v1/authenticate/{service_id}"
    url = await authenticate_service(service_id, code, redirect_uri)
    return redirect(url)


@twitchalerts_ext.route("/api/v1/createdonation", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "name": {"type": "string"},
        "sats": {"type": "integer", "required": True},
        "service": {"type": "integer", "required": True},
        "cur_code": {"type": "string", "required": True},
        "amount": {"type": "float", "required": True}
    }
)
async def api_create_donation():
    """Takes data from donation form and creates+returns SatsPay charge"""
    webhook_base = request.scheme + "://" + request.headers["Host"]
    charge_details = await get_charge_details(g.data["service"])
    name = g.data.get("name", "Anonymous")
    charge = await create_charge(
        amount=g.data["sats"],
        completelink="https://twitch.tv/Fitti",
        completelinktext="Back to Stream!",
        webhook=webhook_base + "/twitchalerts/api/v1/postdonation",
        **charge_details)
    await create_donation(
        id=charge.id,
        name=name,
        cur_code=g.data["cur_code"],
        sats=g.data["sats"],
        amount=g.data["amount"],
        service=g.data["service"],
    )
    return redirect(f"/satspay/{charge.id}")


@twitchalerts_ext.route("/api/v1/postdonation", methods=["POST"])
@api_validate_post_request(
    schema={
        "id": {"type": "string", "required": True},
    }
)
async def api_post_donation():
    """Posts a paid donation to Stremalabs/StreamElements.

    This endpoint acts as a webhook for the SatsPayServer extension."""
    data = await request.get_json(force=True)
    donation_id = data.get("id", "No ID")
    charge = await get_charge(donation_id)
    print(charge)
    if charge and charge.paid:
        print("This endpoint works!")
        if await post_donation(donation_id):
            return (
                jsonify({"message": "Posted!"}),
                HTTPStatus.OK
            )
        else:
            return (
                jsonify({"message": "Already posted!"}),
                HTTPStatus.BAD_REQUEST
            )
    else:
        return (
            jsonify({"message": "Not a paid charge!"}),
            HTTPStatus.BAD_REQUEST
        )
