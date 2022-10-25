from http import HTTPStatus

from fastapi import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.extensions.subdomains.models import CreateDomain, CreateSubdomain

from . import subdomains_ext
from .cloudflare import cloudflare_create_subdomain, cloudflare_deletesubdomain
from .crud import (
    create_domain,
    create_subdomain,
    delete_domain,
    delete_subdomain,
    get_domain,
    get_domains,
    get_subdomain,
    get_subdomainBySubdomain,
    get_subdomains,
    update_domain,
)

# domainS


@subdomains_ext.get("/api/v1/domains")
async def api_domains(
    g: WalletTypeInfo = Depends(get_key_type),  # type: ignore
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        user = await get_user(g.wallet.user)
        if user is not None:
            wallet_ids = user.wallet_ids

    return [domain.dict() for domain in await get_domains(wallet_ids)]


@subdomains_ext.post("/api/v1/domains")
@subdomains_ext.put("/api/v1/domains/{domain_id}")
async def api_domain_create(
    data: CreateDomain,
    domain_id=None,
    g: WalletTypeInfo = Depends(get_key_type),  # type: ignore
):
    if domain_id:
        domain = await get_domain(domain_id)

        if not domain:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
            )
        if domain.wallet != g.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your domain."
            )

        domain = await update_domain(domain_id, **data.dict())
    else:
        domain = await create_domain(data=data)
    return domain.dict()


@subdomains_ext.delete("/api/v1/domains/{domain_id}")
async def api_domain_delete(
    domain_id, g: WalletTypeInfo = Depends(get_key_type)  # type: ignore
):
    domain = await get_domain(domain_id)

    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
        )
    if domain.wallet != g.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your domain.")

    await delete_domain(domain_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


#########subdomains##########


@subdomains_ext.get("/api/v1/subdomains")
async def api_subdomains(
    all_wallets: bool = Query(False), g: WalletTypeInfo = Depends(get_key_type)  # type: ignore
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        user = await get_user(g.wallet.user)
        if user is not None:
            wallet_ids = user.wallet_ids

    return [domain.dict() for domain in await get_subdomains(wallet_ids)]


@subdomains_ext.post("/api/v1/subdomains/{domain_id}")
async def api_subdomain_make_subdomain(domain_id, data: CreateSubdomain):
    domain = await get_domain(domain_id)

    # If the request is coming for the non-existant domain
    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNsubdomain does not exist."
        )
    ## If record_type is not one of the allowed ones reject the request
    if data.record_type not in domain.allowed_record_types:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{data.record_type} not a valid record.",
        )

    ## If domain already exist in our database reject it
    if await get_subdomainBySubdomain(data.subdomain) is not None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{data.subdomain}.{domain.domain} domain already taken.",
        )

    ## Dry run cloudflare... (create and if create is sucessful delete it)
    cf_response = await cloudflare_create_subdomain(
        domain=domain,
        subdomain=data.subdomain,
        record_type=data.record_type,
        ip=data.ip,
    )
    if cf_response["success"] == True:
        await cloudflare_deletesubdomain(
            domain=domain, domain_id=cf_response["result"]["id"]
        )
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f'Problem with cloudflare: {cf_response["errors"][0]["message"]}',
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
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    subdomain = await create_subdomain(
        payment_hash=payment_hash, wallet=domain.wallet, data=data
    )

    if not subdomain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNsubdomain could not be fetched."
        )

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@subdomains_ext.get("/api/v1/subdomains/{payment_hash}")
async def api_subdomain_send_subdomain(payment_hash):
    subdomain = await get_subdomain(payment_hash)
    try:
        status = await check_transaction_status(subdomain.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return {"paid": False}

    if is_paid:
        return {"paid": True}

    return {"paid": False}


@subdomains_ext.delete("/api/v1/subdomains/{subdomain_id}")
async def api_subdomain_delete(
    subdomain_id, g: WalletTypeInfo = Depends(get_key_type)  # type: ignore
):
    subdomain = await get_subdomain(subdomain_id)

    if not subdomain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNsubdomain does not exist."
        )

    if subdomain.wallet != g.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your subdomain."
        )

    await delete_subdomain(subdomain_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
