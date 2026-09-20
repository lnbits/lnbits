import json
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, SecretStr
from starlette.concurrency import run_in_threadpool

from lnbits.core.services.onchain import require_onchain_payments
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import settings

from .crud import (
    WalletAlreadyConfiguredError,
    create_watch_wallet,
    db,
    get_config,
    update_watch_wallet,
)
from .decorators import OnchainAuth, require_onchain_admin
from .helpers import address_script, descriptor_fingerprint, parse_key
from .hot_wallet import (
    HotWalletPayment,
    NewHotWallet,
    decrypt_mnemonic,
    encrypt_mnemonic,
    encryption_key,
    new_mnemonic,
    sign_payment,
    wallet_descriptor,
)
from .models import WalletAccount
from .sync import explorer_client, request_scan
from .views_api import _get_user_watch_wallet, api_get_addresses, ensure_network

hot_wallet_router = APIRouter()


class StoredSecret(BaseModel):
    encrypted_seed: str


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@hot_wallet_router.get("/api/v1/hot-wallet/status")
async def hot_wallet_status(
    _auth: OnchainAuth = Depends(require_onchain_admin),
):
    try:
        await require_onchain_payments()
        encryption_key()
        return {"available": True}
    except ValueError:
        return {"available": False}


@hot_wallet_router.post("/api/v1/hot-wallet", response_model=WalletAccount)
async def create_hot_wallet(
    data: NewHotWallet,
    response: Response,
    recovery_phrase: Annotated[
        SecretStr | None, Header(alias="X-Onchain-Recovery-Phrase")
    ] = None,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    no_store(response)
    await ensure_network(auth.wallet_id, data.network)
    try:
        await require_onchain_payments()
        encryption_key()
    except ValueError as exc:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, str(exc)) from exc
    try:
        mnemonic = await run_in_threadpool(
            new_mnemonic,
            recovery_phrase.get_secret_value() if recovery_phrase else None,
        )
        descriptor, path = await run_in_threadpool(
            wallet_descriptor, mnemonic, data.network
        )
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid recovery phrase") from exc
    if not data.title.strip():
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Enter a wallet name")
    wallet = WalletAccount(
        id=urlsafe_short_hash(),
        wallet_id=auth.wallet_id,
        masterpub=descriptor,
        fingerprint=descriptor_fingerprint(parse_key(descriptor)[0]),
        title=data.title.strip(),
        address_no=-1,
        balance=0,
        type="p2wpkh",
        network=data.network,
        meta=json.dumps({"accountPath": path}),
        wallet_kind="hot",
    )
    encrypted = encrypt_mnemonic(mnemonic, wallet)
    try:
        await create_watch_wallet(wallet, encrypted_seed=encrypted)
    except WalletAlreadyConfiguredError as exc:
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc
    await api_get_addresses(wallet.id, auth)
    request_scan(auth.wallet_id)
    return wallet


async def secret_for_wallet(wallet: WalletAccount) -> str:
    if wallet.wallet_kind != "hot":
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "This wallet uses an external signer"
        )
    row = await db.fetchone(
        "SELECT encrypted_seed FROM onchain_keys WHERE wallet = :wallet",
        {"wallet": wallet.id},
        StoredSecret,
    )
    if not row:
        raise HTTPException(HTTPStatus.CONFLICT, "Wallet key is unavailable")
    return row.encrypted_seed


@hot_wallet_router.post("/api/v1/hot-wallet/{wallet_id}/backup")
async def backup_hot_wallet(
    wallet_id: str,
    response: Response,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    no_store(response)
    wallet = await _get_user_watch_wallet(wallet_id, auth.wallet_id)
    encrypted = await secret_for_wallet(wallet)
    try:
        mnemonic = await run_in_threadpool(decrypt_mnemonic, encrypted, wallet)
        return {"mnemonic": mnemonic, "path": json.loads(wallet.meta)["accountPath"]}
    except ValueError as exc:
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE, "Wallet key cannot be unlocked"
        ) from exc


@hot_wallet_router.post("/api/v1/hot-wallet/{wallet_id}/backup/confirm")
async def confirm_backup(
    wallet_id: str,
    auth: OnchainAuth = Depends(require_onchain_admin),
):
    wallet = await _get_user_watch_wallet(wallet_id, auth.wallet_id)
    await secret_for_wallet(wallet)
    wallet.backup_confirmed = True
    return await update_watch_wallet(wallet)


@hot_wallet_router.post("/api/v1/hot-wallet/{wallet_id}/sign")
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
    wallet = await _get_user_watch_wallet(wallet_id, auth.wallet_id)
    encrypted = await secret_for_wallet(wallet)
    try:
        # Reject spent/stale inputs before asking the signer to use the seed.
        config = await get_config(auth.wallet_id)
        async with explorer_client(config) as client:
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
