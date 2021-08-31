from quart import g, jsonify, request
from http import HTTPStatus
from urllib.parse import urlparse

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import lnaddress_ext
from .crud import (
    # create_subdomain,
    # get_subdomain,
    # get_subdomains,
    # delete_subdomain,
    create_domain,
    update_domain,
    get_domain,
    get_domains,
    delete_domain,
    # get_subdomainBySubdomain,
)

from .cloudflare import cloudflare_create_record, cloudflare_deleterecord

# DOMAINS

@lnaddress_ext.route("/api/v1/domains", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_domains():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    print("URL", urlparse(request.url_root).netloc)
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

        ## Dry run cloudflare... (create and if create is sucessful delete it)
        root_url = urlparse(request.url_root).netloc
        cf_response = await cloudflare_create_subdomain(
            domain=domain,
            ip=root_url,
        )
        if cf_response["success"] == True:
            # cloudflare_deletesubdomain(domain=domain, domain_id=cf_response["result"]["id"])
            domain = await create_domain(**g.data)
        else:
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
