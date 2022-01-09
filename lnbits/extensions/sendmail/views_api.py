from http import HTTPStatus

from fastapi import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import check_invoice_status, create_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.extensions.sendmail.models import CreateEmailaddress, CreateEmail
from .smtp import send_mail, valid_email

from . import sendmail_ext
from .crud import (
    create_emailaddress,
    update_emailaddress,
    delete_emailaddress,
    get_emailaddress,
    get_emailaddress_by_email,
    get_emailaddresses,
    create_email,
    delete_email,
    get_email,
    get_emails,
)

## EMAILS
@sendmail_ext.get("/api/v1/email")
async def api_email(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    return [email.dict() for email in await get_emails(wallet_ids)]

@sendmail_ext.get("/api/v1/email/{payment_hash}")
async def api_sendmail_send_email(payment_hash):
    email = await get_email(payment_hash)
    if not email:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="paymenthash is wrong")

    emailaddress = await get_emailaddress(email.emailaddress_id)

    try:
        status = await check_invoice_status(email.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return {"paid": False}
    if is_paid:
        if emailaddress.anonymize:
            await delete_email(email.id)
        return {"paid": True}
    return {"paid": False}


@sendmail_ext.post("/api/v1/email/{emailaddress_id}")
async def api_sendmail_make_email(emailaddress_id, data: CreateEmail):

    valid_email(data.receiver)

    emailaddress = await get_emailaddress(emailaddress_id)
    # If the request is coming for the non-existant emailaddress
    if not emailaddress:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Emailaddress address does not exist."
        )
    try:
        memo = f"sent email from {emailaddress.email} to {data.receiver}"
        if emailaddress.anonymize:
            memo = "sent email"

        payment_hash, payment_request = await create_invoice(
            wallet_id=emailaddress.wallet,
            amount=emailaddress.cost,
            memo=memo,
            extra={"tag": "lnsendmail"},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    email = await create_email(
        payment_hash=payment_hash, wallet=emailaddress.wallet, data=data
    )

    if not email:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Email could not be fetched."
        )
    return {"payment_hash": payment_hash, "payment_request": payment_request}

@sendmail_ext.delete("/api/v1/email/{email_id}")
async def api_email_delete(email_id, g: WalletTypeInfo = Depends(get_key_type)):
    email = await get_email(email_id)

    if not email:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNsubdomain does not exist."
        )

    if email.wallet != g.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your email."
        )

    await delete_email(email_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


## EMAILADDRESSES
@sendmail_ext.get("/api/v1/emailaddress")
async def api_emailaddresses(
    g: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    return [emailaddress.dict() for emailaddress in await get_emailaddresses(wallet_ids)]


@sendmail_ext.post("/api/v1/emailaddress")
@sendmail_ext.put("/api/v1/emailaddress/{emailaddress_id}")
async def api_emailaddress_create(
    data: CreateEmailaddress, emailaddress_id=None, g: WalletTypeInfo = Depends(get_key_type)
):
    if emailaddress_id:
        emailaddress = await get_emailaddress(emailaddress_id)

        if not emailaddress:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Emailadress does not exist."
            )
        if emailaddress.wallet != g.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your emailaddress."
            )

        emailaddress = await update_emailaddress(emailaddress_id, **data.dict())
    else:
        emailaddress = await create_emailaddress(data=data)
    return emailaddress.dict()


@sendmail_ext.delete("/api/v1/emailaddress/{emailaddress_id}")
async def api_emailaddress_delete(emailaddress_id, g: WalletTypeInfo = Depends(get_key_type)):
    emailaddress = await get_emailaddress(emailaddress_id)

    if not emailaddress:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Emailaddress does not exist."
        )
    if emailaddress.wallet != g.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your Emailaddress.")

    await delete_emailaddress(emailaddress_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)

