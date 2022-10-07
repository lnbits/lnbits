from http import HTTPStatus
from typing import Union

import httpx
from fastapi import Query
from fastapi.params import Depends
from lnurl import decode as decode_lnurl
from loguru import logger
from secp256k1 import PublicKey
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.wallets.base import PaymentStatus

from . import cashu_ext
from .core.base import CashuError
from .crud import (
    create_cashu,
    delete_cashu,
    get_cashu,
    get_cashus,
    get_lightning_invoice,
    store_lightning_invoice,
)
from .ledger import mint, request_mint
from .mint import get_pubkeys
from .models import (
    Cashu,
    CheckPayload,
    Invoice,
    MeltPayload,
    MintPayloads,
    PayLnurlWData,
    Pegs,
    SplitPayload,
)

########################################
#################MINT CRUD##############
########################################

# todo: use /mints
@cashu_ext.get("/api/v1/cashus", status_code=HTTPStatus.OK)
async def api_cashus(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [cashu.dict() for cashu in await get_cashus(wallet_ids)]


@cashu_ext.post("/api/v1/cashus", status_code=HTTPStatus.CREATED)
async def api_cashu_create(data: Cashu, wallet: WalletTypeInfo = Depends(get_key_type)):
    cashu = await create_cashu(wallet_id=wallet.wallet.id, data=data)
    logger.debug(cashu)
    return cashu.dict()


@cashu_ext.post("/api/v1/cashus/upodatekeys", status_code=HTTPStatus.CREATED)
async def api_cashu_update_keys(
    data: Cashu, wallet: WalletTypeInfo = Depends(get_key_type)
):
    cashu = await get_cashu(data.id)

    cashu = await create_cashu(wallet_id=wallet.wallet.id, data=data)
    logger.debug(cashu)
    return cashu.dict()


@cashu_ext.delete("/api/v1/cashus/{cashu_id}")
async def api_cashu_delete(
    cashu_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    cashu = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    if cashu.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your TPoS.")

    await delete_cashu(cashu_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


########################################
#################????###################
########################################
@cashu_ext.post("/api/v1/cashus/{cashu_id}/invoices", status_code=HTTPStatus.CREATED)
async def api_cashu_create_invoice(
    amount: int = Query(..., ge=1), tipAmount: int = None, cashu_id: str = None
):
    cashu = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    if tipAmount:
        amount += tipAmount

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=cashu.wallet,
            amount=amount,
            memo=f"{cashu.name}",
            extra={"tag": "cashu", "tipAmount": tipAmount, "cashuId": cashu_id},
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return {"payment_hash": payment_hash, "payment_request": payment_request}


@cashu_ext.post(
    "/api/v1/cashus/{cashu_id}/invoices/{payment_request}/pay",
    status_code=HTTPStatus.OK,
)
async def api_cashu_pay_invoice(
    lnurl_data: PayLnurlWData, payment_request: str = None, cashu_id: str = None
):
    cashu = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )

    lnurl = (
        lnurl_data.lnurl.replace("lnurlw://", "")
        .replace("lightning://", "")
        .replace("LIGHTNING://", "")
        .replace("lightning:", "")
        .replace("LIGHTNING:", "")
    )

    if lnurl.lower().startswith("lnurl"):
        lnurl = decode_lnurl(lnurl)
    else:
        lnurl = "https://" + lnurl

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(lnurl, follow_redirects=True)
            if r.is_error:
                lnurl_response = {"success": False, "detail": "Error loading"}
            else:
                resp = r.json()
                if resp["tag"] != "withdrawRequest":
                    lnurl_response = {"success": False, "detail": "Wrong tag type"}
                else:
                    r2 = await client.get(
                        resp["callback"],
                        follow_redirects=True,
                        params={
                            "k1": resp["k1"],
                            "pr": payment_request,
                        },
                    )
                    resp2 = r2.json()
                    if r2.is_error:
                        lnurl_response = {
                            "success": False,
                            "detail": "Error loading callback",
                        }
                    elif resp2["status"] == "ERROR":
                        lnurl_response = {"success": False, "detail": resp2["reason"]}
                    else:
                        lnurl_response = {"success": True, "detail": resp2}
        except (httpx.ConnectError, httpx.RequestError):
            lnurl_response = {"success": False, "detail": "Unexpected error occurred"}

    return lnurl_response


@cashu_ext.get(
    "/api/v1/cashus/{cashu_id}/invoices/{payment_hash}", status_code=HTTPStatus.OK
)
async def api_cashu_check_invoice(cashu_id: str, payment_hash: str):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
        )
    try:
        status = await api_payment(payment_hash)

    except Exception as exc:
        logger.error(exc)
        return {"paid": False}
    return status


########################################
#################MINT###################
########################################


@cashu_ext.get("/api/v1/mint/keys/{cashu_id}", status_code=HTTPStatus.OK)
async def keys(
    cashu_id: str = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    """Get the public keys of the mint"""
    mint = await get_cashu(cashu_id)
    if mint is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    return get_pubkeys(mint.prvkey)


@cashu_ext.get("/api/v1/mint/{cashu_id}")
async def mint_pay_request(amount: int = 0, cashu_id: str = Query(None)):
    """Request minting of tokens. Server responds with a Lightning invoice."""

    cashu = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=cashu.wallet,
            amount=amount,
            memo=f"{cashu.name}",
            extra={"tag": "cashu"},
        )
        invoice = Invoice(
            amount=amount, pr=payment_request, hash=payment_hash, issued=False
        )
        await store_lightning_invoice(cashu_id, invoice)
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(cashu_id)
        )

    return {"pr": payment_request, "hash": payment_hash}


@cashu_ext.post("/mint")
async def mint_coins(
    payloads: MintPayloads,
    payment_hash: Union[str, None] = None,
    cashu_id: str = Query(None),
):
    """
    Requests the minting of tokens belonging to a paid payment request.
    Call this endpoint after `GET /mint`.
    """
    print("############################ amount")
    cashu: Cashu = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    invoice: Invoice = get_lightning_invoice(cashu_id, payment_hash)
    if invoice is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not have this invoice."
        )

    status: PaymentStatus = check_transaction_status(cashu.wallet, payment_hash)
    if status.paid == False:
        raise HTTPException(
            status_code=HTTPStatus.PAYMENT_REQUIRED, detail="Invoice not paid."
        )

    # amounts = []
    # B_s = []
    # for payload in payloads.blinded_messages:
    #     amounts.append(payload.amount)
    #     B_s.append(PublicKey(bytes.fromhex(payload.B_), raw=True))
    # try:
    #     promises = await ledger.mint(B_s, amounts, payment_hash=payment_hash)
    #     return promises
    # except Exception as exc:
    #     return CashuError(error=str(exc))


@cashu_ext.post("/melt")
async def melt_coins(payload: MeltPayload, cashu_id: str = Query(None)):

    ok, preimage = await melt(payload.proofs, payload.amount, payload.invoice, cashu_id)
    return {"paid": ok, "preimage": preimage}


@cashu_ext.post("/check")
async def check_spendable_coins(payload: CheckPayload, cashu_id: str = Query(None)):
    return await check_spendable(payload.proofs, cashu_id)


@cashu_ext.post("/split")
async def spli_coinst(payload: SplitPayload, cashu_id: str = Query(None)):
    """
    Requetst a set of tokens with amount "total" to be split into two
    newly minted sets with amount "split" and "total-split".
    """
    proofs = payload.proofs
    amount = payload.amount
    output_data = payload.output_data.blinded_messages
    try:
        split_return = await split(proofs, amount, output_data)
    except Exception as exc:
        return {"error": str(exc)}
    if not split_return:
        """There was a problem with the split"""
        raise Exception("could not split tokens.")
    fst_promises, snd_promises = split_return
    return {"fst": fst_promises, "snd": snd_promises}
