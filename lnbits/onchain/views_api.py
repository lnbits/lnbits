import json
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from lnbits.core.crud.onchain import (
    get_address_by_id,
    get_fresh_address,
    update_address,
)
from lnbits.core.crud.wallets import (
    get_onchain_wallet,
    update_onchain_wallet_config,
)
from lnbits.core.models.onchain import (
    Address,
    CreatePsbt,
    ExtractPsbt,
    ExtractTx,
    SerializedTransaction,
    SignedTransaction,
)
from lnbits.core.models.wallets import OnchainConfig, OnchainWalletConfigResponse
from lnbits.core.services.wallets_onchain import (
    ensure_network,
    get_wallet_addresses,
)
from lnbits.settings import settings

from .bindings import wally
from .decorators import (
    OnchainAuth,
    require_onchain_admin,
    require_onchain_read,
)
from .explorer import explorer_url, local_explorer_network, provider_name
from .helpers import transaction_details
from .psbt import (
    combine_matching_psbt,
    create_psbt,
    finalize_signed_psbt,
    psbt_fee,
    set_previous_transaction,
)
from .sync import explorer_client, request_scan

onchain_api_router = APIRouter()


#############################ADDRESSES##########################


@onchain_api_router.get("/api/v1/address/{wallet_id}")
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


@onchain_api_router.put("/api/v1/address/{address_id}")
async def api_update_address(
    address_id: str,
    req: Request,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    address = await get_address_by_id(address_id)
    if not address or address.wallet != auth.wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    wallet = await get_onchain_wallet(address.wallet)
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


@onchain_api_router.get("/api/v1/addresses/{wallet_id}")
async def api_get_addresses(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_read),
) -> list[Address]:
    if wallet_id != auth.wallet_id:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    return await get_wallet_addresses(wallet_id)


@onchain_api_router.post("/api/v1/psbt")
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


@onchain_api_router.put("/api/v1/psbt/utxos")
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


@onchain_api_router.put("/api/v1/psbt/extract")
async def api_psbt_extract_tx(
    data: ExtractPsbt,
    _auth: OnchainAuth = Depends(require_onchain_admin),
) -> SignedTransaction:
    return await run_in_threadpool(_extract_psbt, data)


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


@onchain_api_router.put("/api/v1/tx/extract")
async def api_extract_tx(
    data: ExtractTx,
    _auth: OnchainAuth = Depends(require_onchain_admin),
):
    return await run_in_threadpool(_extract_transaction, data)


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


@onchain_api_router.post("/api/v1/tx")
async def api_tx_broadcast(
    data: SerializedTransaction,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    if settings.lnbits_only_allow_incoming_payments:
        raise HTTPException(403, "Only incoming payments allowed")
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    await ensure_network(
        auth.wallet_id, data.network or wallet.onchain_network or "Mainnet"
    )
    try:
        async with explorer_client(
            wallet.onchain_config, wallet.onchain_network or "Mainnet"
        ) as client:
            tx_id = await client.broadcast(data.tx_hex)
            from .sync import TXID

            if not TXID.fullmatch(tx_id):
                raise ValueError("Invalid broadcast response")
        request_scan(auth.wallet_id)
        return tx_id
    except Exception as exc:
        raise HTTPException(
            400, "Broadcast failed. Check the transaction status before retrying."
        ) from exc


@onchain_api_router.put("/api/v1/config")
async def api_update_config(
    data: OnchainConfig,
    network: Literal["Mainnet", "Testnet", "Testnet4"] = Query(...),
    auth: OnchainAuth = Depends(require_onchain_admin),
) -> OnchainWalletConfigResponse:
    if data.explorer_provider == "lnbits" and local_explorer_network() != network:
        raise HTTPException(
            400, "LNbits block explorer is unavailable for this network"
        )
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    if wallet.onchain_wallet_kind and wallet.onchain_network != network:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            "Create another LNbits wallet to use a different Bitcoin network",
        )
    await update_onchain_wallet_config(data, wallet_id=auth.wallet_id, network=network)
    request_scan(auth.wallet_id)
    return config_response(data, network)


@onchain_api_router.get("/api/v1/config")
async def api_get_config(
    auth: OnchainAuth = Depends(require_onchain_read),
) -> OnchainWalletConfigResponse:
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    return config_response(wallet.onchain_config, wallet.onchain_network or "Mainnet")


def config_response(config: OnchainConfig, network: str) -> OnchainWalletConfigResponse:
    data = config.dict()
    data["explorer_provider"] = provider_name(config, network)
    data["network"] = network
    return OnchainWalletConfigResponse(
        **data,
        lnbits_explorer_network=local_explorer_network(),
        explorer_url=explorer_url(config, network),
    )
