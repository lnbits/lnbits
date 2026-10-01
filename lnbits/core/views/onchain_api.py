from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from lnbits.core.crud.wallets import (
    WalletAlreadyConfiguredError,
    clear_onchain_wallet_data,
    get_onchain_wallet,
)
from lnbits.core.models.wallets import CreateOnchainWallet, OnchainWallet
from lnbits.core.services.wallets import (
    get_wallet_addresses,
    init_onchain_wallet,
)
from lnbits.onchain.decorators import (
    OnchainAuth,
    require_onchain_admin,
    require_onchain_read,
)
from lnbits.onchain.sync import request_scan

onchain_wallet_router = APIRouter(prefix="/onchain/api/v1", tags=["Onchain"])


@onchain_wallet_router.get("/wallet", response_model_exclude={"adminkey", "inkey"})
async def api_wallets_retrieve(
    network: Literal["Mainnet", "Testnet", "Testnet4"] | None = Query(None),
    auth: OnchainAuth = Depends(require_onchain_read),
) -> OnchainWallet | None:
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet or not wallet.onchain_wallet_kind:
        return None
    if network and wallet.onchain_network != network:
        return None
    return wallet


@onchain_wallet_router.post("/wallet", response_model_exclude={"adminkey", "inkey"})
async def api_wallet_create_or_update(
    data: CreateOnchainWallet,
    auth: OnchainAuth = Depends(require_onchain_admin),
) -> OnchainWallet:
    wallet = await get_onchain_wallet(auth.wallet_id)
    if not wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    if (wallet.onchain_network or "Mainnet") != data.network:
        raise HTTPException(400, "Bitcoin network does not match this LNbits wallet")
    try:
        wallet = await init_onchain_wallet(data, wallet)
    except WalletAlreadyConfiguredError as exc:
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc
    if not wallet or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    await get_wallet_addresses(wallet)
    request_scan(auth.wallet_id)
    return wallet


@onchain_wallet_router.delete("/wallet/{wallet_id}")
async def api_wallet_delete(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    if wallet_id != auth.wallet_id:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    if wallet.onchain_wallet_kind == "hot":
        raise HTTPException(
            HTTPStatus.CONFLICT,
            "Server wallets cannot be deleted while they hold signing keys."
            " Keep the wallet for recovery and transaction history.",
        )
    try:
        await clear_onchain_wallet_data(wallet_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc
    return "", HTTPStatus.NO_CONTENT
