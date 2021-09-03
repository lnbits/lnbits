from quart import g, jsonify, request
from http import HTTPStatus
from urllib.parse import urlparse

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import lnaddress_ext
from .crud import (
    # create_address,
    # get_subdomain,
    get_addresses,
    # delete_subdomain,
    create_domain,
    update_domain,
    get_domain,
    get_domains,
    delete_domain,
    check_address_available
)

from .cloudflare import cloudflare_create_record, cloudflare_deleterecord

# DOMAINS

@lnaddress_ext.route("/api/v1/domains", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_domains():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([domain._asdict() for domain in await get_domains(wallet_ids)]),
        HTTPStatus.OK,
    )


@lnaddress_ext.route("/api/v1/domains", methods=["POST"])
@lnaddress_ext.route("/api/v1/domains/<domain_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "wallet": {"type": "string", "empty": False, "required": True},
        "domain": {"type": "string", "empty": False, "required": True},
        "cf_token": {"type": "string", "empty": False, "required": True},
        "cf_zone_id": {"type": "string", "empty": False, "required": True},
        "webhook": {"type": "string", "empty": False, "required": False},
        "cost": {"type": "integer", "min": 0, "required": True},
    }
)
async def api_domain_create(domain_id=None):
    if domain_id:
        domain = await get_domain(domain_id)

        if not domain:
            return jsonify({"message": "domain does not exist."}), HTTPStatus.NOT_FOUND

        if domain.wallet != g.wallet.id:
            return jsonify({"message": "Not your domain."}), HTTPStatus.FORBIDDEN

        domain = await update_domain(domain_id, **g.data)
    else:

        domain = await create_domain(**g.data)
        root_url = request.url_root

        cf_response = await cloudflare_create_record(
            domain=domain,
            ip=root_url,
        )

        if not cf_response or cf_response["success"] != True:
            await delete_domain(domain.id)
            return (
                jsonify(
                    {
                        "message": "Problem with cloudflare: "
                        + cf_response["errors"][0]["message"]
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )

    return jsonify(domain._asdict()), HTTPStatus.CREATED

@lnaddress_ext.route("/api/v1/domains/<domain_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_domain_delete(domain_id):
    domain = await get_domain(domain_id)

    if not domain:
        return jsonify({"message": "domain does not exist."}), HTTPStatus.NOT_FOUND

    if domain.wallet != g.wallet.id:
        return jsonify({"message": "Not your domain."}), HTTPStatus.FORBIDDEN

    await delete_domain(domain_id)

    return "", HTTPStatus.NO_CONTENT

# ADDRESSES

@lnaddress_ext.route("/api/v1/addresses", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_addresses():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([domain._asdict() for domain in await get_addresses(wallet_ids)]),
        HTTPStatus.OK,
    )

@lnaddress_ext.route("/api/v1/address/availabity/<domain_id>/<username>", methods=["GET"])
async def api_check_available_username(domain_id, username):
    used_username = await check_address_available(username, domain_id)
    # if used_username < 1:
    #     return jsonify(True)
    return jsonify(used_username)

@lnaddress_ext.route("/api/v1/address/<domain_id>", methods=["POST"])
@api_validate_post_request(
    schema={
        "domain": {"type": "string", "empty": False, "required": True},
        "username": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": True, "required": False},
        "wallet_endpoint": {"type": "string", "empty": False, "required": True},
        "wallet_key": {"type": "string", "empty": False, "required": True},
        "sats": {"type": "integer", "min": 0, "required": True},
        "duration": {"type": "integer", "empty": False, "required": True}
    }
)
async def api_lnaddress_make_address(domain_id):
    domain = await get_domain(domain_id)

    # If the request is coming for the non-existant domain
    if not domain:
        return jsonify({"message": "The domain does not exist."}), HTTPStatus.NOT_FOUND

    used_username = await check_address_available(g.data["username"], g.data["domain"])
    if not used_username:
        print("OK", used_username)
    ## ALL OK - create an invoice and return it to the user
    # sats = g.data["sats"]
    #
    # try:
    #     payment_hash, payment_request = await create_invoice(
    #         wallet_id=domain.wallet,
    #         amount=sats,
    #         memo=f"subdomain {g.data['subdomain']}.{domain.domain} for {sats} sats for {g.data['duration']} days",
    #         extra={"tag": "lnsubdomain"},
    #     )
    # except Exception as e:
    #     return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR
    #
    # subdomain = await create_subdomain(
    #     payment_hash=payment_hash, wallet=domain.wallet, **g.data
    # )
    #
    # if not subdomain:
    #     return (
    #         jsonify({"message": "LNsubdomain could not be fetched."}),
    #         HTTPStatus.NOT_FOUND,
    #     )
    #
    # return (
    #     jsonify({"payment_hash": payment_hash, "payment_request": payment_request}),
    #     HTTPStatus.OK,
    # )
