import math
from http import HTTPStatus
from typing import Dict, List, Union

# -------- cashu imports
from cashu.core.base import (
    CheckFeesRequest,
    CheckFeesResponse,
    CheckSpendableRequest,
    CheckSpendableResponse,
    GetMeltResponse,
    GetMintResponse,
    Invoice,
    PostMeltRequest,
    PostMintRequest,
    PostMintResponse,
    PostSplitRequest,
    PostSplitResponse,
)
from fastapi import Depends, Query
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits import bolt11
from lnbits.core.crud import check_internal, get_user
from lnbits.core.services import (
    check_transaction_status,
    create_invoice,
    fee_reserve,
    pay_invoice,
)
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.helpers import urlsafe_short_hash
from lnbits.wallets.base import PaymentStatus

from . import cashu_ext, ledger
from .crud import create_cashu, delete_cashu, get_cashu, get_cashus
from .models import Cashu

# --------- extension imports

# WARNING: Do not set this to False in production! This will create
# tokens for free otherwise. This is for testing purposes only!

LIGHTNING = True

if not LIGHTNING:
    logger.warning(
        "Cashu: LIGHTNING is set False! That means that I will create ecash for free!"
    )

########################################
############### LNBITS MINTS ###########
########################################


@cashu_ext.get("/api/v1/mints", status_code=HTTPStatus.OK)
async def api_cashus(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    """
    Get all mints of this wallet.
    """
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        if user:
            wallet_ids = user.wallet_ids

    return [cashu.dict() for cashu in await get_cashus(wallet_ids)]


@cashu_ext.post("/api/v1/mints", status_code=HTTPStatus.CREATED)
async def api_cashu_create(
    data: Cashu,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    """
    Create a new mint for this wallet.
    """
    cashu_id = urlsafe_short_hash()
    # generate a new keyset in cashu
    keyset = await ledger.load_keyset(cashu_id)

    cashu = await create_cashu(
        cashu_id=cashu_id, keyset_id=keyset.id, wallet_id=wallet.wallet.id, data=data
    )
    logger.debug(cashu)
    return cashu.dict()


@cashu_ext.delete("/api/v1/mints/{cashu_id}")
async def api_cashu_delete(
    cashu_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    """
    Delete an existing cashu mint.
    """
    cashu = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Cashu mint does not exist."
        )

    if cashu.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your Cashu mint."
        )

    await delete_cashu(cashu_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


#######################################
########### CASHU ENDPOINTS ###########
#######################################


@cashu_ext.get("/api/v1/{cashu_id}/keys", status_code=HTTPStatus.OK)
async def keys(cashu_id: str = Query(None)) -> dict[int, str]:
    """Get the public keys of the mint"""
    cashu: Union[Cashu, None] = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    return ledger.get_keyset(keyset_id=cashu.keyset_id)


@cashu_ext.get("/api/v1/{cashu_id}/keys/{idBase64Urlsafe}")
async def keyset_keys(
    cashu_id: str = Query(None), idBase64Urlsafe: str = Query(None)
) -> dict[int, str]:
    """
    Get the public keys of the mint of a specificy keyset id.
    The id is encoded in base64_urlsafe and needs to be converted back to
    normal base64 before it can be processed.
    """

    cashu: Union[Cashu, None] = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    id = idBase64Urlsafe.replace("-", "+").replace("_", "/")
    keyset = ledger.get_keyset(keyset_id=id)
    return keyset


@cashu_ext.get("/api/v1/{cashu_id}/keysets", status_code=HTTPStatus.OK)
async def keysets(cashu_id: str = Query(None)) -> dict[str, list[str]]:
    """Get the public keys of the mint"""
    cashu: Union[Cashu, None] = await get_cashu(cashu_id)

    if not cashu:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    return {"keysets": [cashu.keyset_id]}


@cashu_ext.get("/api/v1/{cashu_id}/mint")
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


@cashu_ext.post("/api/v1/{cashu_id}/mint")
async def mint(
    data: PostMintRequest,
    cashu_id: str = Query(None),
    payment_hash: str = Query(None),
) -> PostMintResponse:
    """
    Requests the minting of tokens belonging to a paid payment request.
    Call this endpoint after `GET /mint`.
    """
    cashu: Union[Cashu, None] = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )

    keyset = ledger.keysets.keysets[cashu.keyset_id]

    if LIGHTNING:
        invoice: Invoice = await ledger.crud.get_lightning_invoice(
            db=ledger.db, hash=payment_hash
        )
        if invoice is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Mint does not know this invoice.",
            )
        if invoice.issued:
            raise HTTPException(
                status_code=HTTPStatus.PAYMENT_REQUIRED,
                detail="Tokens already issued for this invoice.",
            )

        # set this invoice as issued
        await ledger.crud.update_lightning_invoice(
            db=ledger.db, hash=payment_hash, issued=True
        )

        status: PaymentStatus = await check_transaction_status(
            cashu.wallet, payment_hash
        )

        try:
            total_requested = sum([bm.amount for bm in data.outputs])
            if total_requested > invoice.amount:
                raise HTTPException(
                    status_code=HTTPStatus.PAYMENT_REQUIRED,
                    detail=f"Requested amount too high: {total_requested}. Invoice amount: {invoice.amount}",
                )

            if not status.paid:
                raise HTTPException(
                    status_code=HTTPStatus.PAYMENT_REQUIRED, detail="Invoice not paid."
                )

            promises = await ledger._generate_promises(B_s=data.outputs, keyset=keyset)
            return PostMintResponse(promises=promises)
        except (Exception, HTTPException) as e:
            logger.debug(f"Cashu: /melt {str(e) or getattr(e, 'detail')}")
            # unset issued flag because something went wrong
            await ledger.crud.update_lightning_invoice(
                db=ledger.db, hash=payment_hash, issued=False
            )
            raise HTTPException(
                status_code=getattr(e, "status_code")
                or HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=str(e) or getattr(e, "detail"),
            )
    else:
        # only used for testing when LIGHTNING=false
        promises = await ledger._generate_promises(B_s=data.outputs, keyset=keyset)
        return PostMintResponse(promises=promises)


@cashu_ext.post("/api/v1/{cashu_id}/melt")
async def melt_coins(
    payload: PostMeltRequest, cashu_id: str = Query(None)
) -> GetMeltResponse:
    """Invalidates proofs and pays a Lightning invoice."""
    cashu: Union[None, Cashu] = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    proofs = payload.proofs
    invoice = payload.pr

    # !!!!!!! MAKE SURE THAT PROOFS ARE ONLY FROM THIS CASHU KEYSET ID
    # THIS IS NECESSARY BECAUSE THE CASHU BACKEND WILL ACCEPT ANY VALID
    # TOKENS
    assert all([p.id == cashu.keyset_id for p in proofs]), HTTPException(
        status_code=HTTPStatus.METHOD_NOT_ALLOWED,
        detail="Error: Tokens are from another mint.",
    )

    # set proofs as pending
    await ledger._set_proofs_pending(proofs)

    try:
        await ledger._verify_proofs(proofs)

        total_provided = sum([p["amount"] for p in proofs])
        invoice_obj = bolt11.decode(invoice)
        amount = math.ceil(invoice_obj.amount_msat / 1000)

        internal_checking_id = await check_internal(invoice_obj.payment_hash)

        if not internal_checking_id:
            fees_msat = fee_reserve(invoice_obj.amount_msat)
        else:
            fees_msat = 0
        assert total_provided >= amount + math.ceil(fees_msat / 1000), Exception(
            f"Provided proofs ({total_provided} sats) not enough for Lightning payment ({amount + fees_msat} sats)."
        )
        logger.debug(f"Cashu: Initiating payment of {total_provided} sats")
        try:
            await pay_invoice(
                wallet_id=cashu.wallet,
                payment_request=invoice,
                description=f"Pay cashu invoice",
                extra={"tag": "cashu", "cashu_name": cashu.name},
            )
        except Exception as e:
            logger.debug(f"Cashu error paying invoice {invoice_obj.payment_hash}: {e}")
            raise e
        finally:
            logger.debug(
                f"Cashu: Wallet {cashu.wallet} checking PaymentStatus of {invoice_obj.payment_hash}"
            )
            status: PaymentStatus = await check_transaction_status(
                cashu.wallet, invoice_obj.payment_hash
            )
            if status.paid == True:
                logger.debug(
                    f"Cashu: Payment successful, invalidating proofs for {invoice_obj.payment_hash}"
                )
                await ledger._invalidate_proofs(proofs)
            else:
                logger.debug(f"Cashu: Payment failed for {invoice_obj.payment_hash}")
    except Exception as e:
        logger.debug(f"Cashu: Exception: {str(e)}")
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Cashu: {str(e)}",
        )
    finally:
        logger.debug(f"Cashu: Unset pending")
        # delete proofs from pending list
        await ledger._unset_proofs_pending(proofs)

    return GetMeltResponse(paid=status.paid, preimage=status.preimage)


@cashu_ext.post("/api/v1/{cashu_id}/check")
async def check_spendable(
    payload: CheckSpendableRequest, cashu_id: str = Query(None)
) -> Dict[int, bool]:
    """Check whether a secret has been spent already or not."""
    cashu: Union[None, Cashu] = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    spendableList = await ledger.check_spendable(payload.proofs)
    return CheckSpendableResponse(spendable=spendableList)


@cashu_ext.post("/api/v1/{cashu_id}/checkfees")
async def check_fees(
    payload: CheckFeesRequest, cashu_id: str = Query(None)
) -> CheckFeesResponse:
    """
    Responds with the fees necessary to pay a Lightning invoice.
    Used by wallets for figuring out the fees they need to supply.
    This is can be useful for checking whether an invoice is internal (Cashu-to-Cashu).
    """
    cashu: Union[None, Cashu] = await get_cashu(cashu_id)
    if cashu is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Mint does not exist."
        )
    invoice_obj = bolt11.decode(payload.pr)
    internal_checking_id = await check_internal(invoice_obj.payment_hash)

    if not internal_checking_id:
        fees_msat = fee_reserve(invoice_obj.amount_msat)
    else:
        fees_msat = 0
    return CheckFeesResponse(fee=math.ceil(fees_msat / 1000))


@cashu_ext.post("/api/v1/{cashu_id}/split")
async def split(
    payload: PostSplitRequest, cashu_id: str = Query(None)
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

    # !!!!!!! MAKE SURE THAT PROOFS ARE ONLY FROM THIS CASHU KEYSET ID
    # THIS IS NECESSARY BECAUSE THE CASHU BACKEND WILL ACCEPT ANY VALID
    # TOKENS
    if not all([p.id == cashu.keyset_id for p in proofs]):
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED,
            detail="Error: Tokens are from another mint.",
        )

    amount = payload.amount
    outputs = payload.outputs
    assert outputs, Exception("no outputs provided.")
    split_return = None
    try:
        keyset = ledger.keysets.keysets[cashu.keyset_id]
        split_return = await ledger.split(proofs, amount, outputs, keyset)
    except Exception as exc:
        raise HTTPException(
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
