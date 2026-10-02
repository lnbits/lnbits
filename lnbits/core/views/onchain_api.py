import json
import re
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import SecretStr
from starlette.concurrency import run_in_threadpool

from lnbits.core.crud.onchain import get_address_by_id, update_address
from lnbits.core.crud.wallets import (
    WalletAlreadyConfiguredError,
    get_onchain_encrypted_seed,
    get_onchain_wallet,
    init_onchain_wallet_state,
    update_onchain_wallet,
)
from lnbits.core.models.onchain import (
    Address,
    CreatePsbt,
    ExtractPsbt,
    ExtractTx,
    HotWalletPayment,
    SerializedTransaction,
    SignedTransaction,
)
from lnbits.core.models.wallets import NewHotWallet, OnchainMeta, OnchainWallet
from lnbits.core.services.blockexplorer import TXID, explorer_client
from lnbits.core.services.onchain import (
    decrypt_wallet_mnemonic,
    encrypt_wallet_mnemonic,
    get_fresh_address,
    get_onchain_daily_stats,
    get_wallet_state,
    read_onchain_key,
    request_scan,
    require_onchain_payments,
    sign_payment,
)
from lnbits.core.services.wallets import get_wallet_addresses
from lnbits.decorators import (
    OnchainAuth,
    require_onchain_admin,
    require_onchain_read,
)
from lnbits.settings import settings
from lnbits.utils.onchain import (
    address_script,
    combine_matching_psbt,
    create_psbt,
    descriptor_fingerprint,
    finalize_signed_psbt,
    new_mnemonic,
    parse_key,
    psbt_fee,
    set_previous_transaction,
    transaction_details,
    wallet_descriptor,
    wally,
)

onchain_router = APIRouter(prefix="/api/v1/onchain", tags=["Onchain"])


#############################ADDRESSES##########################


@onchain_router.get("/address/{wallet_id}")
async def api_fresh_address(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_read),
) -> Address:
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or wallet_id != auth.wallet_id or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    if wallet.onchain_wallet_kind == "hot" and not wallet.onchain_backup_confirmed:
        raise HTTPException(HTTPStatus.CONFLICT, "Back up this wallet before receiving")
    address = await get_fresh_address(wallet_id)
    assert address
    return address


@onchain_router.put("/address/{address_id}")
async def api_update_address(
    address_id: str,
    req: Request,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    address = await get_address_by_id(address_id)
    if not address or address.walet_id != auth.wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    wallet = await get_onchain_wallet(address.walet_id)
    if not wallet or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")

    body = await req.json()
    if "amount" in body:
        raise HTTPException(400, "Balances are updated only by the blockchain scanner")
    if "note" in body:
        if not isinstance(body["note"], str) or len(body["note"]) > 500:
            raise HTTPException(400, "Address note must be at most 500 characters")
        address.note = body["note"]
    address = await update_address(address)
    return address


@onchain_router.get("/addresses/{wallet_id}")
async def api_get_addresses(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_read),
) -> list[Address]:
    if wallet_id != auth.wallet_id:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    return await get_wallet_addresses(wallet)


@onchain_router.post("/psbt")
async def api_psbt_create(
    data: CreatePsbt,
    _auth: OnchainAuth = Depends(require_onchain_admin),
):
    try:
        return await run_in_threadpool(
            lambda: wally.psbt_to_base64(create_psbt(data), 0)
        )

    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@onchain_router.put("/psbt/utxos")
async def api_psbt_utxos_tx(
    req: Request,
    _auth: OnchainAuth = Depends(require_onchain_admin),
):
    """Extract previous unspent transaction outputs (tx_id, vout) from PSBT"""

    body = await req.json()
    try:
        psbt = wally.psbt_from_base64(body["psbtBase64"], 0)
        res = []
        for index in range(wally.psbt_get_num_inputs(psbt)):
            res.append(
                {
                    "tx_id": bytes(wally.psbt_get_input_previous_txid(psbt, index))[
                        ::-1
                    ].hex(),
                    "vout": wally.psbt_get_input_output_index(psbt, index),
                }
            )

        return res
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@onchain_router.put("/psbt/extract")
async def api_psbt_extract_tx(
    data: ExtractPsbt,
    _auth: OnchainAuth = Depends(require_onchain_admin),
) -> SignedTransaction:
    return await run_in_threadpool(_extract_psbt, data)


@onchain_router.put("/tx/extract")
async def api_extract_tx(
    data: ExtractTx,
    _auth: OnchainAuth = Depends(require_onchain_admin),
):
    return await run_in_threadpool(_extract_transaction, data)


@onchain_router.post("/tx")
async def api_tx_broadcast(
    data: SerializedTransaction,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    if settings.lnbits_only_allow_incoming_payments:
        raise HTTPException(403, "Only incoming payments allowed")
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    if data.network and (wallet.onchain_network or "Mainnet") != data.network:
        raise HTTPException(400, "Bitcoin network does not match this LNbits wallet")
    try:
        async with explorer_client(
            wallet.onchain_config, wallet.onchain_network or "Mainnet"
        ) as client:
            tx_id = await client.broadcast(data.tx_hex)
            if not TXID.fullmatch(tx_id):
                raise ValueError("Invalid broadcast response")
        request_scan(auth.wallet_id)
        return tx_id
    except Exception as exc:
        raise HTTPException(
            400, "Broadcast failed. Check the transaction status before retrying."
        ) from exc


@onchain_router.get("/hot-wallet/status")
async def hot_wallet_status(
    _auth: OnchainAuth = Depends(require_onchain_admin),
):
    try:
        await require_onchain_payments()
        read_onchain_key()
        return {"available": True}
    except ValueError:
        return {"available": False}


@onchain_router.post(
    "/hot-wallet",
    response_model=OnchainWallet,
    response_model_exclude={"adminkey", "inkey"},
)
async def create_hot_wallet(
    data: NewHotWallet,
    response: Response,
    recovery_phrase: Annotated[
        SecretStr | None, Header(alias="X-Onchain-Recovery-Phrase")
    ] = None,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    no_store(response)
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    if (wallet.onchain_network or "Mainnet") != data.network:
        raise HTTPException(400, "Bitcoin network does not match this LNbits wallet")
    try:
        await require_onchain_payments()
        read_onchain_key()
    except ValueError as exc:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, str(exc)) from exc
    try:
        mnemonic = await run_in_threadpool(
            new_mnemonic,
            recovery_phrase.get_secret_value() if recovery_phrase else None,
        )
        descriptor, path = await run_in_threadpool(
            wallet_descriptor,
            mnemonic,
            data.network,
            data.script_type,
            data.account_path,
        )
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid recovery phrase") from exc
    if not data.title.strip():
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Enter a wallet name")
    wallet.name = data.title.strip()
    wallet.onchain_network = data.network
    wallet.onchain_wallet_kind = "hot"
    wallet.onchain_meta = OnchainMeta(
        masterpub=descriptor,
        fingerprint=descriptor_fingerprint(parse_key(descriptor)[0]),
        script_type=data.script_type,
        accountPath=path,
    )
    encrypted = encrypt_wallet_mnemonic(mnemonic, wallet)
    try:
        wallet = await init_onchain_wallet_state(wallet, encrypted_seed=encrypted)
    except WalletAlreadyConfiguredError as exc:
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    if not wallet or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    await get_wallet_addresses(wallet)
    request_scan(auth.wallet_id)
    return wallet


@onchain_router.post("/hot-wallet/{wallet_id}/backup")
async def backup_hot_wallet(
    wallet_id: str,
    response: Response,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    no_store(response)
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or wallet_id != auth.wallet_id or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    encrypted = await secret_for_wallet(wallet)
    try:
        mnemonic = await run_in_threadpool(decrypt_wallet_mnemonic, encrypted, wallet)
        return {"mnemonic": mnemonic, "path": wallet.onchain_meta.accountPath}
    except ValueError as exc:
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE, "Wallet key cannot be unlocked"
        ) from exc


@onchain_router.post(
    "/hot-wallet/{wallet_id}/backup/confirm",
    response_model=OnchainWallet,
    response_model_exclude={"adminkey", "inkey"},
)
async def confirm_backup(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or wallet_id != auth.wallet_id or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    await secret_for_wallet(wallet)
    wallet.onchain_backup_confirmed = True
    return await update_onchain_wallet(wallet)


@onchain_router.post("/hot-wallet/{wallet_id}/sign")
async def sign_hot_wallet_payment(
    wallet_id: str,
    data: HotWalletPayment,
    response: Response,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    no_store(response)
    if settings.lnbits_only_allow_incoming_payments:
        raise HTTPException(403, "Only incoming payments allowed")
    try:
        await require_onchain_payments()
    except ValueError as exc:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, str(exc)) from exc
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or wallet_id != auth.wallet_id or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    encrypted = await secret_for_wallet(wallet)
    try:
        # Reject spent/stale inputs before asking the signer to use the seed.
        async with explorer_client(
            wallet.onchain_config, wallet.onchain_network or "Mainnet"
        ) as client:
            for address in {i.address for i in data.transaction.inputs}:
                address_script(address)
                utxos = await client.utxos(address)
                available = {(u["txid"], u["vout"], u["value"]) for u in utxos}
                if any(
                    (i.tx_id, i.vout, i.amount) not in available
                    for i in data.transaction.inputs
                    if i.address == address
                ):
                    raise ValueError("Inputs have changed")
        return await run_in_threadpool(sign_payment, wallet, encrypted, data)
    except Exception as exc:
        # Native library/encryption errors must not disclose key material.
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "Cannot sign: check wallet backup, recipients, inputs, network and fee. "
            "If these are correct, ask the administrator to check "
            "the wallet encryption key.",
        ) from exc


@onchain_router.post("/sync", status_code=202)
async def start_sync(auth: OnchainAuth = Depends(require_onchain_admin)):
    request_scan(auth.wallet_id)
    return {"scheduled": True}


@onchain_router.get("/state")
async def wallet_state(auth: OnchainAuth = Depends(require_onchain_read)):
    return await get_wallet_state(auth.wallet_id)


@onchain_router.get("/stats/daily")
async def daily_stats(auth: OnchainAuth = Depends(require_onchain_read)):
    return await get_onchain_daily_stats(auth.wallet_id)


@onchain_router.get("/fees")
async def fee_estimates(auth: OnchainAuth = Depends(require_onchain_read)):
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(404, "Onchain wallet not found")
    try:
        async with explorer_client(
            wallet.onchain_config, wallet.onchain_network or "Mainnet"
        ) as client:
            return await client.fees()
    except Exception as exc:
        raise HTTPException(503, "Fee estimates are unavailable") from exc


@onchain_router.get("/tx/{tx_id}/hex")
async def previous_transaction(
    tx_id: str, auth: OnchainAuth = Depends(require_onchain_read)
):
    if not TXID.fullmatch(tx_id):
        raise HTTPException(400, "Invalid transaction ID")
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(404, "Onchain wallet not found")
    try:
        async with explorer_client(
            wallet.onchain_config, wallet.onchain_network or "Mainnet"
        ) as client:
            raw = await client.raw_transaction(tx_id)
            if len(raw) > 8_000_000 or not re.fullmatch(r"[0-9a-fA-F]+", raw):
                raise ValueError("Invalid transaction")
            return raw
    except Exception as exc:
        raise HTTPException(503, "Previous transaction is unavailable") from exc


def _extract_psbt(data: ExtractPsbt) -> SignedTransaction:
    network = (
        wally.WALLY_NETWORK_BITCOIN_MAINNET
        if data.network == "Mainnet"
        else wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    try:
        psbt = wally.psbt_from_base64(data.psbt_base64, 0)
        if data.expected_psbt_base64:
            expected = wally.psbt_from_base64(data.expected_psbt_base64, 0)
            psbt = combine_matching_psbt(expected, psbt)
        for i, inp in enumerate(data.inputs):
            set_previous_transaction(psbt, i, inp.tx_hex)

        fee = psbt_fee(psbt)
        transaction = finalize_signed_psbt(psbt)
        tx_hex = wally.tx_to_hex(transaction, wally.WALLY_TX_FLAG_USE_WITNESS)
        tx = transaction_details(transaction, network)
        tx["fee"] = fee
        signed_tx = SignedTransaction(tx_hex=tx_hex, tx_json=json.dumps(tx))
        return signed_tx
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


def _extract_transaction(data: ExtractTx):
    network = (
        wally.WALLY_NETWORK_BITCOIN_MAINNET
        if data.network == "Mainnet"
        else wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    try:
        transaction = wally.tx_from_hex(data.tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
        tx = transaction_details(transaction, network)
        return {"tx_json": tx}
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


async def secret_for_wallet(wallet: OnchainWallet) -> str:
    if wallet.onchain_wallet_kind != "hot":
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "This wallet uses an external signer"
        )
    encrypted_seed = await get_onchain_encrypted_seed(wallet.id)
    if encrypted_seed is None:
        raise HTTPException(HTTPStatus.CONFLICT, "Wallet key is unavailable")
    return encrypted_seed
