import json
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import settings

from .bindings import wally
from .crud import (
    WalletAlreadyConfiguredError,
    create_fresh_addresses,
    create_watch_wallet,
    db,
    delete_addresses_for_wallet,
    delete_watch_wallet,
    get_address_by_id,
    get_addresses,
    get_config,
    get_fresh_address,
    get_watch_wallet,
    get_watch_wallets,
    update_address,
    update_config,
)
from .decorators import (
    OnchainAuth,
    require_onchain_admin,
    require_onchain_read,
)
from .explorer import explorer_url, local_explorer_network, provider_name
from .helpers import (
    descriptor_fingerprint,
    descriptor_type,
    parse_key,
    transaction_details,
)
from .models import (
    Address,
    Config,
    ConfigResponse,
    CreatePsbt,
    CreateWallet,
    ExtractPsbt,
    ExtractTx,
    SerializedTransaction,
    SignedTransaction,
    WalletAccount,
)
from .psbt import (
    combine_matching_psbt,
    create_psbt,
    finalize_signed_psbt,
    psbt_fee,
    set_previous_transaction,
)
from .sync import explorer_client, request_scan

onchain_api_router = APIRouter()


@onchain_api_router.get("/api/v1/wallet")
async def api_wallets_retrieve(
    network: Literal["Mainnet", "Testnet", "Testnet4"] | None = Query(None),
    auth: OnchainAuth = Depends(require_onchain_read),
) -> list[WalletAccount]:
    config = await get_config(auth.wallet_id)
    return await get_watch_wallets(auth.wallet_id, network or config.network)


@onchain_api_router.get("/api/v1/wallet/{wallet_id}")
async def api_wallet_retrieve(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_read),
) -> WalletAccount:
    return await _get_user_watch_wallet(wallet_id, auth.wallet_id)


@onchain_api_router.post("/api/v1/wallet")
async def api_wallet_create_or_update(
    data: CreateWallet,
    auth: OnchainAuth = Depends(require_onchain_admin),
) -> WalletAccount:
    await ensure_network(auth.wallet_id, data.network)
    try:
        descriptor, network = await run_in_threadpool(parse_key, data.masterpub)
        assert network
        signing_network = "Testnet" if data.network == "Testnet4" else data.network
        if signing_network != network["name"]:
            raise ValueError(
                "Account network error.  This account is for '{}'".format(
                    network["name"]
                )
            )

        new_wallet = WalletAccount(
            id=urlsafe_short_hash(),
            wallet_id=auth.wallet_id,
            masterpub=data.masterpub,
            fingerprint=descriptor_fingerprint(descriptor),
            type=descriptor_type(descriptor),
            title=data.title,
            address_no=-1,  # fresh address on empty wallet can get address with index 0
            balance=0,
            network=data.network,
            meta=data.meta,
        )

        wallet = await create_watch_wallet(new_wallet)

        await api_get_addresses(wallet.id, auth)
        request_scan(auth.wallet_id)
    except WalletAlreadyConfiguredError as exc:
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc

    return wallet


@onchain_api_router.delete("/api/v1/wallet/{wallet_id}")
async def api_wallet_delete(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    wallet = await _get_user_watch_wallet(wallet_id, auth.wallet_id)
    if wallet.wallet_kind == "hot":
        raise HTTPException(
            HTTPStatus.CONFLICT,
            "Server wallets cannot be deleted while they hold signing keys."
            " Keep the wallet for recovery and transaction history.",
        )
    await db.execute(
        """
        DELETE FROM onchain_snapshots WHERE address_id IN (
            SELECT id FROM onchain_addresses WHERE wallet = :wallet
        )
    """,
        {"wallet": wallet_id},
    )
    await delete_addresses_for_wallet(wallet_id)
    await delete_watch_wallet(wallet_id)

    return "", HTTPStatus.NO_CONTENT


#############################ADDRESSES##########################


@onchain_api_router.get("/api/v1/address/{wallet_id}")
async def api_fresh_address(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_read),
) -> Address:
    wallet = await _get_user_watch_wallet(wallet_id, auth.wallet_id)
    if wallet.wallet_kind == "hot" and not wallet.backup_confirmed:
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
    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    await _get_user_watch_wallet(address.wallet, auth.wallet_id)

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
    await _get_user_watch_wallet(wallet_id, auth.wallet_id)

    addresses = await get_addresses(wallet_id)
    config = await get_config(auth.wallet_id)
    assert config, "Config not found"

    if not addresses:
        await create_fresh_addresses(wallet_id, 0, config.receive_gap_limit)
        await create_fresh_addresses(wallet_id, 0, config.change_gap_limit, True)
        addresses = await get_addresses(wallet_id)

    receive_addresses = list(filter(lambda addr: addr.branch_index == 0, addresses))
    change_addresses = list(filter(lambda addr: addr.branch_index == 1, addresses))

    last_receive_address = list(
        filter(lambda addr: addr.has_activity, receive_addresses)
    )[-1:]
    last_change_address = list(
        filter(lambda addr: addr.has_activity, change_addresses)
    )[-1:]

    if last_receive_address:
        current_index = receive_addresses[-1].address_index
        address_index = last_receive_address[0].address_index
        await create_fresh_addresses(
            wallet_id, current_index + 1, address_index + config.receive_gap_limit + 1
        )

    if last_change_address:
        current_index = change_addresses[-1].address_index
        address_index = last_change_address[0].address_index
        await create_fresh_addresses(
            wallet_id,
            current_index + 1,
            address_index + config.change_gap_limit + 1,
            True,
        )

    return await get_addresses(wallet_id)


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
    config = await get_config(auth.wallet_id)
    await ensure_network(auth.wallet_id, data.network or config.network)
    try:
        async with explorer_client(config) as client:
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
    data: Config,
    auth: OnchainAuth = Depends(require_onchain_admin),
) -> ConfigResponse:
    previous = await get_config(auth.wallet_id)
    if previous.network != data.network:
        rows: list[dict] = await db.fetchall(
            "SELECT id FROM onchain_accounts WHERE wallet_id = :id",
            {"id": auth.wallet_id},
        )
        if rows:
            raise HTTPException(
                409, "Create another LNbits wallet to use a different Bitcoin network"
            )
    if data.explorer_provider == "lnbits" and local_explorer_network() != data.network:
        raise HTTPException(
            400, "LNbits block explorer is unavailable for this network"
        )
    config = await update_config(data, wallet_id=auth.wallet_id)
    request_scan(auth.wallet_id)
    return config_response(config)


@onchain_api_router.get("/api/v1/config")
async def api_get_config(
    auth: OnchainAuth = Depends(require_onchain_read),
) -> ConfigResponse:
    config = await get_config(auth.wallet_id)
    return config_response(config)


def config_response(config: Config) -> ConfigResponse:
    data = config.dict()
    data["explorer_provider"] = provider_name(config)
    return ConfigResponse(
        **data,
        lnbits_explorer_network=local_explorer_network(),
        explorer_url=explorer_url(config),
    )


async def _get_user_watch_wallet(wallet_id: str, user_id: str) -> WalletAccount:
    watch_wallet = await get_watch_wallet(wallet_id)

    if not watch_wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    if watch_wallet.wallet_id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    return watch_wallet


async def ensure_network(wallet_id: str, network: str) -> None:
    config = await get_config(wallet_id)
    if config.network != network:
        raise HTTPException(400, "Bitcoin network does not match this LNbits wallet")
