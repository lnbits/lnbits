import json
from http import HTTPStatus
from typing import Union
import math
from typing import Dict, List, Union

import httpx
from fastapi import Query
from fastapi.params import Depends
from lnurl import decode as decode_lnurl
from loguru import logger
from secp256k1 import PublicKey
from starlette.exceptions import HTTPException
from lnbits import bolt11

from lnbits.core.crud import get_user
from lnbits.core.services import (
    check_transaction_status,
    create_invoice,
    fee_reserve,
    pay_invoice,
)

from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.wallets.base import PaymentStatus
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.crud import check_internal

# --------- extension imports

from . import cashu_ext
from .crud import (
    create_cashu,
    delete_cashu,
    get_cashu,
    get_cashus,
)

from .models import Cashu

from . import ledger

# -------- cashu imports
from cashu.core.base import (
    Proof,
    BlindedSignature,
    CheckFeesRequest,
    CheckFeesResponse,
    CheckRequest,
    GetMeltResponse,
    GetMintResponse,
    MeltRequest,
    MintRequest,
    PostSplitResponse,
    SplitRequest,
    Invoice,
)

LIGHTNING = False

########################################
############### LNBITS MINTS ###########
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
    cashu_id = urlsafe_short_hash()
    # generate a new keyset in cashu
    keyset = await ledger.load_keyset(cashu_id)

    cashu = await create_cashu(
        cashu_id=cashu_id, keyset_id=keyset.id, wallet_id=wallet.wallet.id, data=data
    )
    logger.debug(cashu)
    return cashu.dict()


#######################################
########### CASHU ENDPOINTS ###########
#######################################


@cashu_ext.get("/api/v1/cashu/{cashu_id}/keys", status_code=HTTPStatus.OK)
async def keys(cashu_id: str = Query(None)) -> dict[int, str]:
    """Get the public keys of the mint"""
    cashu: Union[Cashu, None] = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    return ledger.get_keyset(keyset_id=cashu.keyset_id)


@cashu_ext.get("/api/v1/cashu/{cashu_id}/mint")
async def request_mint(cashu_id: str = Query(None), amount: int = 0) -> GetMintResponse:
    """
    Request minting of new tokens. The mint responds with a Lightning invoice.
    This endpoint can be used for a Lightning invoice UX flow.

    Call `POST /mint` after paying the invoice.
    """
    cashu: Union[Cashu, None] = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    # create an invoice that the wallet needs to pay
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
        # await store_lightning_invoice(cashu_id, invoice)
        await ledger.crud.store_lightning_invoice(invoice=invoice, db=ledger.db)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    print(f"Lightning invoice: {payment_request}")
    resp = GetMintResponse(pr=payment_request, hash=payment_hash)
    #     return {"pr": payment_request, "hash": payment_hash}
    return resp


@cashu_ext.post("/api/v1/cashu/{cashu_id}/mint")
async def mint_coins(
    data: MintRequest,
    cashu_id: str = Query(None),
    payment_hash: str = Query(None),
) -> List[BlindedSignature]:
    """
    Requests the minting of tokens belonging to a paid payment request.
    Call this endpoint after `GET /mint`.
    """
    cashu: Union[Cashu, None] = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    if LIGHTNING:
        invoice: Invoice = await ledger.crud.get_lightning_invoice(
            db=ledger.db, hash=payment_hash
        )
        if invoice is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Mint does not have this invoice.",
            )
        if invoice.issued == True:
            raise HTTPException(
                status_code=HTTPStatus.PAYMENT_REQUIRED,
                detail="Tokens already issued for this invoice.",
            )

        total_requested = sum([bm.amount for bm in data.blinded_messages])
        if total_requested > invoice.amount:
            raise HTTPException(
                status_code=HTTPStatus.PAYMENT_REQUIRED,
                detail=f"Requested amount too high: {total_requested}. Invoice amount: {invoice.amount}",
            )

    status: PaymentStatus = await check_transaction_status(cashu.wallet, payment_hash)
    # todo: revert to: status.paid != True:
    if status.paid != True:
        raise HTTPException(
            status_code=HTTPStatus.PAYMENT_REQUIRED, detail="Invoice not paid."
        )
    try:
        await ledger.crud.update_lightning_invoice(
            db=ledger.db, hash=payment_hash, issued=True
        )
        keyset = ledger.keysets.keysets[cashu.keyset_id]

        promises = await ledger._generate_promises(
            B_s=data.blinded_messages, keyset=keyset
        )
        return promises
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))


@cashu_ext.post("/api/v1/cashu/{cashu_id}/melt")
async def melt_coins(
    payload: MeltRequest, cashu_id: str = Query(None)
) -> GetMeltResponse:
    """Invalidates proofs and pays a Lightning invoice."""
    cashu: Union[None, Cashu] = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    proofs = payload.proofs
    invoice = payload.invoice

    # !!!!!!! MAKE SURE THAT PROOFS ARE ONLY FROM THIS CASHU KEYSET ID
    # THIS IS NECESSARY BECAUSE THE CASHU BACKEND WILL ACCEPT ANY VALID
    # TOKENS
    assert all([p.id == cashu.keyset_id for p in proofs]), HTTPException(
        status_code=HTTPStatus.BAD_REQUEST,
        detail="Proofs include tokens from other mint.",
    )

    assert all([ledger._verify_proof(p) for p in proofs]), HTTPException(
        status_code=HTTPStatus.BAD_REQUEST,
        detail="Could not verify proofs.",
    )

    total_provided = sum([p["amount"] for p in proofs])
    invoice_obj = bolt11.decode(invoice)
    amount = math.ceil(invoice_obj.amount_msat / 1000)

    internal_checking_id = await check_internal(invoice_obj.payment_hash)

    if not internal_checking_id:
        fees_msat = fee_reserve(invoice_obj.amount_msat)
    else:
        fees_msat = 0
    assert total_provided >= amount + fees_msat / 1000, Exception(
        f"Provided proofs ({total_provided} sats) not enough for Lightning payment ({amount + fees_msat} sats)."
    )

    await pay_invoice(
        wallet_id=cashu.wallet,
        payment_request=invoice,
        description=f"pay cashu invoice",
        extra={"tag": "cashu", "cahsu_name": cashu.name},
    )

    status: PaymentStatus = await check_transaction_status(
        cashu.wallet, invoice_obj.payment_hash
    )
    if status.paid == True:
        await ledger._invalidate_proofs(proofs)
    return GetMeltResponse(paid=status.paid, preimage=status.preimage)


@cashu_ext.post("/api/v1/check")
async def check_spendable(payload: CheckRequest) -> Dict[int, bool]:
    """Check whether a secret has been spent already or not."""
    return await ledger.check_spendable(payload.proofs)


@cashu_ext.post("/api/v1/checkfees")
async def check_fees(payload: CheckFeesRequest) -> CheckFeesResponse:
    """
    Responds with the fees necessary to pay a Lightning invoice.
    Used by wallets for figuring out the fees they need to supply.
    This is can be useful for checking whether an invoice is internal (Cashu-to-Cashu).
    """
    invoice_obj = bolt11.decode(payload.pr)
    internal_checking_id = await check_internal(invoice_obj.payment_hash)

    if not internal_checking_id:
        fees_msat = fee_reserve(invoice_obj.amount_msat)
    else:
        fees_msat = 0
    return CheckFeesResponse(fee=fees_msat / 1000)


@cashu_ext.post("/api/v1/cashu/{cashu_id}/split")
async def split(
    payload: SplitRequest, cashu_id: str = Query(None)
) -> PostSplitResponse:
    """
    Requetst a set of tokens with amount "total" to be split into two
    newly minted sets with amount "split" and "total-split".
    """
    cashu: Union[None, Cashu] = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    proofs = payload.proofs
    amount = payload.amount
    outputs = payload.outputs.blinded_messages
    # backwards compatibility with clients < v0.2.2
    assert outputs, Exception("no outputs provided.")
    split_return = None
    try:
        split_return = await ledger.split(proofs, amount, outputs, cashu.keyset_id)
    except Exception as exc:
        HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(exc),
        )
    if not split_return:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="there was an error with the split",
        )
    frst_promises, scnd_promises = split_return
    resp = PostSplitResponse(fst=frst_promises, snd=scnd_promises)
    return resp


# @cashu_ext.post("/api/v1s/upodatekeys", status_code=HTTPStatus.CREATED)
# async def api_cashu_update_keys(
#     data: Cashu, wallet: WalletTypeInfo = Depends(get_key_type)
# ):
#     cashu = await get_cashu(data.id)

#     cashu = await create_cashu(wallet_id=wallet.wallet.id, data=data)
#     logger.debug(cashu)
#     return cashu.dict()


# @cashu_ext.delete("/api/v1s/{cashu_id}")
# async def api_cashu_delete(
#     cashu_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
# ):
#     cashu = await get_cashu(cashu_id)

#     if not cashu:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="Cashu does not exist."
#         )

#     if cashu.wallet != wallet.wallet.id:
#         raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your Cashu.")

#     await delete_cashu(cashu_id)
#     raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


# ########################################
# #################????###################
# ########################################
# @cashu_ext.post("/api/v1s/{cashu_id}/invoices", status_code=HTTPStatus.CREATED)
# async def api_cashu_create_invoice(
#     amount: int = Query(..., ge=1), tipAmount: int = None, cashu_id: str = None
# ):
#     cashu = await get_cashu(cashu_id)

#     if not cashu:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
#         )

#     if tipAmount:
#         amount += tipAmount

#     try:
#         payment_hash, payment_request = await create_invoice(
#             wallet_id=cashu.wallet,
#             amount=amount,
#             memo=f"{cashu.name}",
#             extra={"tag": "cashu", "tipAmount": tipAmount, "cashuId": cashu_id},
#         )
#     except Exception as e:
#         raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

#     return {"payment_hash": payment_hash, "payment_request": payment_request}


# @cashu_ext.post(
#     "/api/v1s/{cashu_id}/invoices/{payment_request}/pay",
#     status_code=HTTPStatus.OK,
# )
# async def api_cashu_pay_invoice(
#     lnurl_data: PayLnurlWData, payment_request: str = None, cashu_id: str = None
# ):
#     cashu = await get_cashu(cashu_id)

#     if not cashu:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
#         )

#     lnurl = (
#         lnurl_data.lnurl.replace("lnurlw://", "")
#         .replace("lightning://", "")
#         .replace("LIGHTNING://", "")
#         .replace("lightning:", "")
#         .replace("LIGHTNING:", "")
#     )

#     if lnurl.lower().startswith("lnurl"):
#         lnurl = decode_lnurl(lnurl)
#     else:
#         lnurl = "https://" + lnurl

#     async with httpx.AsyncClient() as client:
#         try:
#             r = await client.get(lnurl, follow_redirects=True)
#             if r.is_error:
#                 lnurl_response = {"success": False, "detail": "Error loading"}
#             else:
#                 resp = r.json()
#                 if resp["tag"] != "withdrawRequest":
#                     lnurl_response = {"success": False, "detail": "Wrong tag type"}
#                 else:
#                     r2 = await client.get(
#                         resp["callback"],
#                         follow_redirects=True,
#                         params={
#                             "k1": resp["k1"],
#                             "pr": payment_request,
#                         },
#                     )
#                     resp2 = r2.json()
#                     if r2.is_error:
#                         lnurl_response = {
#                             "success": False,
#                             "detail": "Error loading callback",
#                         }
#                     elif resp2["status"] == "ERROR":
#                         lnurl_response = {"success": False, "detail": resp2["reason"]}
#                     else:
#                         lnurl_response = {"success": True, "detail": resp2}
#         except (httpx.ConnectError, httpx.RequestError):
#             lnurl_response = {"success": False, "detail": "Unexpected error occurred"}

#     return lnurl_response


# @cashu_ext.get(
#     "/api/v1s/{cashu_id}/invoices/{payment_hash}", status_code=HTTPStatus.OK
# )
# async def api_cashu_check_invoice(cashu_id: str, payment_hash: str):
#     cashu = await get_cashu(cashu_id)
#     if not cashu:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="TPoS does not exist."
#         )
#     try:
#         status = await api_payment(payment_hash)

#     except Exception as exc:
#         logger.error(exc)
#         return {"paid": False}
#     return status


# ########################################
# #################MINT###################
# ########################################


# # @cashu_ext.get("/api/v1/{cashu_id}/keys", status_code=HTTPStatus.OK)
# # async def keys(cashu_id: str = Query(False)):
# #     """Get the public keys of the mint"""
# #     mint = await get_cashu(cashu_id)
# #     if mint is None:
# #         raise HTTPException(
# #             status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
# #         )
# #     return get_pubkeys(mint.prvkey)


# @cashu_ext.get("/api/v1/{cashu_id}/mint")
# async def mint_pay_request(amount: int = 0, cashu_id: str = Query(None)):
#     """Request minting of tokens. Server responds with a Lightning invoice."""

#     cashu = await get_cashu(cashu_id)
#     if cashu is None:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
#         )

#     try:
#         payment_hash, payment_request = await create_invoice(
#             wallet_id=cashu.wallet,
#             amount=amount,
#             memo=f"{cashu.name}",
#             extra={"tag": "cashu"},
#         )
#         invoice = Invoice(
#             amount=amount, pr=payment_request, hash=payment_hash, issued=False
#         )
#         await store_lightning_invoice(cashu_id, invoice)
#     except Exception as e:
#         logger.error(e)
#         raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

#     return {"pr": payment_request, "hash": payment_hash}


# @cashu_ext.post("/api/v1/{cashu_id}/mint")
# async def mint_coins(
#     data: MintPayloads,
#     cashu_id: str = Query(None),
#     payment_hash: Union[str, None] = None,
# ):
#     """
#     Requests the minting of tokens belonging to a paid payment request.
#     Call this endpoint after `GET /mint`.
#     """
#     cashu: Cashu = await get_cashu(cashu_id)
#     if cashu is None:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
#         )
#     invoice: Invoice = (
#         None
#         if payment_hash == None
#         else await get_lightning_invoice(cashu_id, payment_hash)
#     )
#     if invoice is None:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="Mint does not have this invoice."
#         )
#     if invoice.issued == True:
#         raise HTTPException(
#             status_code=HTTPStatus.PAYMENT_REQUIRED,
#             detail="Tokens already issued for this invoice.",
#         )

#     total_requested = sum([bm.amount for bm in data.blinded_messages])
#     if total_requested > invoice.amount:
#         raise HTTPException(
#             status_code=HTTPStatus.PAYMENT_REQUIRED,
#             detail=f"Requested amount too high: {total_requested}. Invoice amount: {invoice.amount}",
#         )

#     status: PaymentStatus = await check_transaction_status(cashu.wallet, payment_hash)
#     # todo: revert to: status.paid != True:
#     if status.paid != True:
#         raise HTTPException(
#             status_code=HTTPStatus.PAYMENT_REQUIRED, detail="Invoice not paid."
#         )
#     try:
#         await update_lightning_invoice(cashu_id, payment_hash, True)

#         amounts = []
#         B_s = []
#         for payload in data.blinded_messages:
#             amounts.append(payload.amount)
#             B_s.append(PublicKey(bytes.fromhex(payload.B_), raw=True))

#         promises = await generate_promises(cashu.prvkey, amounts, B_s)
#         for amount, B_, p in zip(amounts, B_s, promises):
#             await store_promise(amount, B_.serialize().hex(), p.C_, cashu_id)

#         return promises
#     except Exception as e:
#         logger.error(e)
#         raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))


# @cashu_ext.post("/api/v1/{cashu_id}/melt")
# async def melt_coins(payload: MeltPayload, cashu_id: str = Query(None)):
#     """Invalidates proofs and pays a Lightning invoice."""
#     cashu: Cashu = await get_cashu(cashu_id)
#     if cashu is None:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
#         )
#     try:
#         ok, preimage = await melt(cashu, payload.proofs, payload.invoice)
#         return {"paid": ok, "preimage": preimage}
#     except Exception as e:
#         logger.error(e)
#         raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))


# @cashu_ext.post("/api/v1/{cashu_id}/check")
# async def check_spendable_coins(payload: CheckPayload, cashu_id: str = Query(None)):
#     return await check_spendable(payload.proofs, cashu_id)


# @cashu_ext.post("/api/v1/{cashu_id}/split")
# async def split_proofs(payload: SplitRequest, cashu_id: str = Query(None)):
#     """
#     Requetst a set of tokens with amount "total" to be split into two
#     newly minted sets with amount "split" and "total-split".
#     """
#     print("### RECEIVE")
#     print("payload", json.dumps(payload, default=vars))
#     cashu: Cashu = await get_cashu(cashu_id)
#     if cashu is None:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
#         )
#     proofs = payload.proofs
#     amount = payload.amount
#     outputs = payload.outputs.blinded_messages if payload.outputs else None
#     try:
#         split_return = await split(cashu, proofs, amount, outputs)
#     except Exception as exc:
#         raise CashuError(error=str(exc))
#     if not split_return:
#         return {"error": "there was a problem with the split."}
#     frst_promises, scnd_promises = split_return
#     resp = PostSplitResponse(fst=frst_promises, snd=scnd_promises)
#     print("### resp", json.dumps(resp, default=vars))
#     return resp


##################################################################
##################################################################
# CASHU LIB
##################################################################
