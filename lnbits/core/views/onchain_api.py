from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from lnbits.core.crud.wallets_onchain import (
    WalletAlreadyConfiguredError,
    get_onchain_wallet,
)
from lnbits.core.models.wallets import CreateOnchainWallet, OnchainWallet
from lnbits.core.services.wallets_onchain import (
    clear_onchain_wallet_data,
    ensure_network,
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
    await ensure_network(auth.wallet_id, data.network)
    try:
        wallet = await init_onchain_wallet(data, auth.wallet_id)
        request_scan(auth.wallet_id)
        return wallet
    except WalletAlreadyConfiguredError as exc:
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@onchain_wallet_router.delete("/wallet/{wallet_id}")
async def api_wallet_delete(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    await clear_onchain_wallet_data(wallet_id, auth.wallet_id)
    return "", HTTPStatus.NO_CONTENT
