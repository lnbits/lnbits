from typing import Optional
from fastapi.param_functions import Query
from pydantic.main import BaseModel
from quart import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import subdomains_ext
from .crud import (
    create_subdomain,
    get_subdomain,
    get_subdomains,
    delete_subdomain,
    create_domain,
    update_domain,
    get_domain,
    get_domains,
    delete_domain,
    get_subdomainBySubdomain,
)
from .cloudflare import cloudflare_create_subdomain, cloudflare_deletesubdomain


# domainS


@subdomains_ext.get("/api/v1/domains")
@api_check_wallet_key("invoice")
async def api_domains():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        [domain._asdict() for domain in await get_domains(wallet_ids)],
        HTTPStatus.OK,
    )

class CreateDomainsData(BaseModel):
    wallet:  str
    domain:  str
    cf_token:  str
    cf_zone_id:  str
    webhook:  Optional[str]
    description:  str
    cost:  int
    allowed_record_types:  str

@subdomains_ext.post("/api/v1/domains")
@subdomains_ext.put("/api/v1/domains/<domain_id>")
@api_check_wallet_key("invoice")
async def api_domain_create(data: CreateDomainsData, domain_id=None):
    if domain_id:
        domain = await get_domain(domain_id)

        if not domain:
            return {"message": "domain does not exist."}, HTTPStatus.NOT_FOUND

        if domain.wallet != g.wallet.id:
            return {"message": "Not your domain."}, HTTPStatus.FORBIDDEN

        domain = await update_domain(domain_id, **data)
    else:
        domain = await create_domain(**data)
    return jsonify(domain._asdict()), HTTPStatus.CREATED


@subdomains_ext.delete("/api/v1/domains/<domain_id>")
@api_check_wallet_key("invoice")
async def api_domain_delete(domain_id):
    domain = await get_domain(domain_id)

    if not domain:
        return {"message": "domain does not exist."}, HTTPStatus.NOT_FOUND

    if domain.wallet != g.wallet.id:
        return {"message": "Not your domain."}, HTTPStatus.FORBIDDEN

    await delete_domain(domain_id)

    return "", HTTPStatus.NO_CONTENT


#########subdomains##########


@subdomains_ext.get("/api/v1/subdomains")
@api_check_wallet_key("invoice")
async def api_subdomains():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        [domain._asdict() for domain in await get_subdomains(wallet_ids)],
        HTTPStatus.OK,
    )

class CreateDomainsData(BaseModel):
    domain:  str
    subdomain:  str
    email:  str
    ip:  str
    sats:  int = Query(0, ge=0)
    duration:  int
    record_type:  str

@subdomains_ext.post("/api/v1/subdomains/<domain_id>")

async def api_subdomain_make_subdomain(data: CreateDomainsData, domain_id):
    domain = await get_domain(domain_id)

    # If the request is coming for the non-existant domain
    if not domain:
        return jsonify({"message": "LNsubdomain does not exist."}), HTTPStatus.NOT_FOUND

    ## If record_type is not one of the allowed ones reject the request
    if data.record_type not in domain.allowed_record_types:
        return ({"message": data.record_type + "Not a valid record"},
            HTTPStatus.BAD_REQUEST,
        )

    ## If domain already exist in our database reject it
    if await get_subdomainBySubdomain(data.subdomain) is not None:
        return (
                {
                    "message": data.subdomain
                    + "."
                    + domain.domain
                    + " domain already taken"
                },
            HTTPStatus.BAD_REQUEST,
        )

    ## Dry run cloudflare... (create and if create is sucessful delete it)
    cf_response = await cloudflare_create_subdomain(
        domain=domain,
        subdomain=data.subdomain,
        record_type=data.record_type,
        ip=data.ip,
    )
    if cf_response["success"] == True:
        cloudflare_deletesubdomain(domain=domain, domain_id=cf_response["result"]["id"])
    else:
        return (
                {
                    "message": "Problem with cloudflare: "
                    + cf_response["errors"][0]["message"]
                },
            HTTPStatus.BAD_REQUEST,
        )

    ## ALL OK - create an invoice and return it to the user
    sats = data.sats

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=domain.wallet,
            amount=sats,
            memo=f"subdomain {data.subdomain}.{domain.domain} for {sats} sats for {data.duration} days",
            extra={"tag": "lnsubdomain"},
        )
    except Exception as e:
        return {"message": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR

    subdomain = await create_subdomain(
        payment_hash=payment_hash, wallet=domain.wallet, **data
    )

    if not subdomain:
        return (
            {"message": "LNsubdomain could not be fetched."},
            HTTPStatus.NOT_FOUND,
        )

    return (
        {"payment_hash": payment_hash, "payment_request": payment_request},
        HTTPStatus.OK,
    )


@subdomains_ext.get("/api/v1/subdomains/<payment_hash>")
async def api_subdomain_send_subdomain(payment_hash):
    subdomain = await get_subdomain(payment_hash)
    try:
        status = await check_invoice_status(subdomain.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return {"paid": False}, HTTPStatus.OK

    if is_paid:
        return {"paid": True}, HTTPStatus.OK

    return {"paid": False}, HTTPStatus.OK


@subdomains_ext.delete("/api/v1/subdomains/<subdomain_id>")
@api_check_wallet_key("invoice")
async def api_subdomain_delete(subdomain_id):
    subdomain = await get_subdomain(subdomain_id)

    if not subdomain:
        return {"message": "Paywall does not exist."}, HTTPStatus.NOT_FOUND

    if subdomain.wallet != g.wallet.id:
        return {"message": "Not your subdomain."}, HTTPStatus.FORBIDDEN

    await delete_subdomain(subdomain_id)

    return "", HTTPStatus.NO_CONTENT
