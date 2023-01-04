import re
from http import HTTPStatus

from fastapi import Depends, Query
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.extensions.lnticket.models import CreateFormData, CreateTicketData

from . import lnticket_ext
from .crud import (
    create_form,
    create_ticket,
    delete_form,
    delete_ticket,
    get_form,
    get_forms,
    get_ticket,
    get_tickets,
    set_ticket_paid,
    update_form,
)

# FORMS


@lnticket_ext.get("/api/v1/forms")
async def api_forms_get(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [form.dict() for form in await get_forms(wallet_ids)]


@lnticket_ext.post("/api/v1/forms", status_code=HTTPStatus.CREATED)
@lnticket_ext.put("/api/v1/forms/{form_id}")
async def api_form_create(
    data: CreateFormData, form_id=None, wallet: WalletTypeInfo = Depends(get_key_type)
):
    if form_id:
        form = await get_form(form_id)

        if not form:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail=f"Form does not exist."
            )

        if form.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail=f"Not your form."
            )

        form = await update_form(form_id, **data.dict())
    else:
        form = await create_form(data, wallet.wallet)
    return form.dict()


@lnticket_ext.delete("/api/v1/forms/{form_id}")
async def api_form_delete(form_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    form = await get_form(form_id)

    if not form:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Form does not exist."
        )

    if form.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=f"Not your form.")

    await delete_form(form_id)

    return "", HTTPStatus.NO_CONTENT


#########tickets##########


@lnticket_ext.get("/api/v1/tickets")
async def api_tickets(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [form.dict() for form in await get_tickets(wallet_ids)]


@lnticket_ext.post("/api/v1/tickets/{form_id}", status_code=HTTPStatus.CREATED)
async def api_ticket_make_ticket(data: CreateTicketData, form_id):
    form = await get_form(form_id)
    if not form:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"LNTicket does not exist."
        )
    if data.sats < 1:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"0 invoices not allowed."
        )

    nwords = len(re.split(r"\s+", data.ltext))

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=form.wallet,
            amount=data.sats,
            memo=f"ticket with {nwords} words on {form_id}",
            extra={"tag": "lnticket"},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    ticket = await create_ticket(
        payment_hash=payment_hash, wallet=form.wallet, data=data
    )

    if not ticket:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNTicket could not be fetched."
        )

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@lnticket_ext.get("/api/v1/tickets/{payment_hash}", status_code=HTTPStatus.OK)
async def api_ticket_send_ticket(payment_hash):
    ticket = await get_ticket(payment_hash)

    try:
        status = await api_payment(payment_hash)
        if status["paid"]:
            await set_ticket_paid(payment_hash=payment_hash)
            return {"paid": True}
    except Exception:
        return {"paid": False}

    return {"paid": False}


@lnticket_ext.delete("/api/v1/tickets/{ticket_id}")
async def api_ticket_delete(ticket_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    ticket = await get_ticket(ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"LNTicket does not exist."
        )

    if ticket.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your ticket.")

    await delete_ticket(ticket_id)
    return "", HTTPStatus.NO_CONTENT
