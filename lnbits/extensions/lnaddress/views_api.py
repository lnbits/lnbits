from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import Request
from fastapi.params import Depends, Query
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.extensions.lnaddress.models import CreateAddress, CreateDomain

from . import lnaddress_ext
from .cloudflare import cloudflare_create_record, cloudflare_deleterecord
from .crud import (
    check_address_available,
    create_address,
    create_domain,
    delete_address,
    delete_domain,
    get_address,
    get_address_by_username,
    get_addresses,
    get_domain,
    get_domains,
    update_domain,
)


# DOMAINS
@lnaddress_ext.get("/api/v1/domains")
async def api_domains(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [domain.dict() for domain in await get_domains(wallet_ids)]


@lnaddress_ext.post("/api/v1/domains")
@lnaddress_ext.put("/api/v1/domains/{domain_id}")
async def api_domain_create(
    request: Request,
    data: CreateDomain,
    domain_id=None,
    g: WalletTypeInfo = Depends(get_key_type),
):
    if domain_id:
        domain = await get_domain(domain_id)

        if not domain:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
            )

        if domain.wallet != g.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your domain"
            )

        domain = await update_domain(domain_id, **data.dict())
    else:

        domain = await create_domain(data=data)
        root_url = urlparse(str(request.url)).netloc

        cf_response = await cloudflare_create_record(domain=domain, ip=root_url)

        if not cf_response or cf_response["success"] != True:
            await delete_domain(domain.id)
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Problem with cloudflare: "
                + cf_response["errors"][0]["message"],
            )

    return domain.dict()


@lnaddress_ext.delete("/api/v1/domains/{domain_id}")
async def api_domain_delete(domain_id, g: WalletTypeInfo = Depends(get_key_type)):
    domain = await get_domain(domain_id)

    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
        )

    if domain.wallet != g.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your domain")

    await delete_domain(domain_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# ADDRESSES


@lnaddress_ext.get("/api/v1/addresses")
async def api_addresses(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [address.dict() for address in await get_addresses(wallet_ids)]


@lnaddress_ext.get("/api/v1/address/availabity/{domain_id}/{username}")
async def api_check_available_username(domain_id, username):
    used_username = await check_address_available(username, domain_id)

    return used_username


@lnaddress_ext.get("/api/v1/address/{domain}/{username}/{wallet_key}")
async def api_get_user_info(username, wallet_key, domain):
    address = await get_address_by_username(username, domain)

    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    if address.wallet_key != wallet_key:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Incorrect user/wallet information.",
        )

    return address.dict()


@lnaddress_ext.post("/api/v1/address/{domain_id}")
@lnaddress_ext.put("/api/v1/address/{domain_id}/{user}/{wallet_key}")
async def api_lnaddress_make_address(
    domain_id, data: CreateAddress, user=None, wallet_key=None
):
    domain = await get_domain(domain_id)

    # If the request is coming for the non-existant domain
    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="The domain does not exist."
        )

    domain_cost = domain.cost
    sats = data.sats

    ## FAILSAFE FOR CREATING ADDRESSES BY API
    if domain_cost * data.duration != data.sats:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="The amount is not correct. Either 'duration', or 'sats' are wrong.",
        )

    if user:
        address = await get_address_by_username(user, domain.domain)

        if not address:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="The address does not exist."
            )

        if address.wallet_key != wallet_key:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your address."
            )

        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=domain.wallet,
                amount=data.sats,
                memo=f"Renew {data.username}@{domain.domain} for {sats} sats for {data.duration} more days",
                extra={
                    "tag": "renew lnaddress",
                    "id": address.id,
                    "duration": data.duration,
                },
            )

        except Exception as e:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)
            )
    else:
        used_username = await check_address_available(data.username, data.domain)
        # If username is already taken
        if used_username:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Alias/username already taken.",
            )

        ## ALL OK - create an invoice and return it to the user

        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=domain.wallet,
                amount=sats,
                memo=f"LNAddress {data.username}@{domain.domain} for {sats} sats for {data.duration} days",
                extra={"tag": "lnaddress"},
            )
        except Exception as e:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)
            )

        address = await create_address(
            payment_hash=payment_hash, wallet=domain.wallet, data=data
        )

        if not address:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="LNAddress could not be fetched.",
            )

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@lnaddress_ext.get("/api/v1/addresses/{payment_hash}")
async def api_address_send_address(payment_hash):
    address = await get_address(payment_hash)
    domain = await get_domain(address.domain)
    try:
        status = await check_transaction_status(domain.wallet, payment_hash)
        is_paid = not status.pending
    except Exception as e:
        return {"paid": False, "error": str(e)}

    if is_paid:
        return {"paid": True}

    return {"paid": False}


@lnaddress_ext.delete("/api/v1/addresses/{address_id}")
async def api_address_delete(address_id, g: WalletTypeInfo = Depends(get_key_type)):
    address = await get_address(address_id)
    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )
    if address.wallet != g.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your address."
        )

    await delete_address(address_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
