from http import HTTPStatus

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from lnbits.core.crud import wallets_onchain as wallets_onchain_crud
from lnbits.core.crud.onchain import create_fresh_addresses, get_addresses
from lnbits.core.crud.wallets_onchain import (
    init_onchain_wallet as init_onchain_wallet_crud,
)
from lnbits.core.models.onchain import Address
from lnbits.core.models.wallets import CreateOnchainWallet, OnchainMeta, OnchainWallet
from lnbits.onchain.helpers import descriptor_fingerprint, descriptor_type, parse_key


async def init_onchain_wallet(
    data: CreateOnchainWallet, wallet_id: str
) -> OnchainWallet:
    descriptor, network = await run_in_threadpool(parse_key, data.masterpub)
    assert network
    signing_network = "Testnet" if data.network == "Testnet4" else data.network
    if signing_network != network["name"]:
        raise ValueError(
            "Account network error.  This account is for '{}'".format(network["name"])
        )

    new_wallet = await get_onchain_wallet(
        wallet_id, wallet_id, include_unconfigured=True
    )
    new_wallet.name = data.title
    new_wallet.onchain_network = data.network
    new_wallet.onchain_wallet_kind = "watch"
    new_wallet.onchain_meta = OnchainMeta(
        accountPath=data.meta.accountPath,
        xpub=data.meta.xpub,
        masterpub=data.masterpub,
        fingerprint=descriptor_fingerprint(descriptor),
        script_type=descriptor_type(descriptor),
    )

    wallet = await init_onchain_wallet_crud(new_wallet)
    await get_wallet_addresses(wallet.id, wallet_id)
    return wallet


async def clear_onchain_wallet_data(wallet_id: str, auth_wallet_id: str) -> None:
    wallet = await get_onchain_wallet(wallet_id, auth_wallet_id)
    if wallet.onchain_wallet_kind == "hot":
        raise HTTPException(
            HTTPStatus.CONFLICT,
            "Server wallets cannot be deleted while they hold signing keys."
            " Keep the wallet for recovery and transaction history.",
        )
    try:
        await wallets_onchain_crud.clear_onchain_wallet_data(wallet_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.CONFLICT, str(exc)) from exc


async def get_onchain_wallet(
    wallet_id: str, auth_wallet_id: str, *, include_unconfigured: bool = False
) -> OnchainWallet:
    wallet = await wallets_onchain_crud.get_onchain_wallet(wallet_id)
    if (
        not wallet
        or wallet.id != auth_wallet_id
        or (not include_unconfigured and not wallet.onchain_wallet_kind)
    ):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )
    return wallet


async def ensure_network(wallet_id: str, network: str) -> None:
    wallet = await get_onchain_wallet(wallet_id, wallet_id, include_unconfigured=True)
    if (wallet.onchain_network or "Mainnet") != network:
        raise HTTPException(400, "Bitcoin network does not match this LNbits wallet")


async def get_wallet_addresses(wallet_id: str, auth_wallet_id: str) -> list[Address]:
    wallet = await get_onchain_wallet(wallet_id, auth_wallet_id)

    addresses = await get_addresses(wallet_id)
    config = wallet.onchain_config

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
