from http import HTTPStatus

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from lnbits.core.crud.onchain import create_fresh_addresses, get_addresses
from lnbits.core.crud.wallets import get_onchain_wallet, init_onchain_wallet_state
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

    new_wallet = await get_onchain_wallet(wallet_id)
    if not new_wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
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

    wallet = await init_onchain_wallet_state(new_wallet)
    if not wallet or not wallet.onchain_wallet_kind:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet does not exist.")
    await get_wallet_addresses(wallet)
    return wallet


async def get_wallet_addresses(wallet: OnchainWallet) -> list[Address]:
    addresses = await get_addresses(wallet.id)
    config = wallet.onchain_config

    if not addresses:
        await create_fresh_addresses(wallet.id, 0, config.receive_gap_limit)
        await create_fresh_addresses(wallet.id, 0, config.change_gap_limit, True)
        addresses = await get_addresses(wallet.id)

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
            wallet.id, current_index + 1, address_index + config.receive_gap_limit + 1
        )

    if last_change_address:
        current_index = change_addresses[-1].address_index
        address_index = last_change_address[0].address_index
        await create_fresh_addresses(
            wallet.id,
            current_index + 1,
            address_index + config.change_gap_limit + 1,
            True,
        )

    return await get_addresses(wallet.id)
